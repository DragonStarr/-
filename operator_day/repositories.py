from __future__ import annotations

from hashlib import sha256
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from operator_day.config import get_settings
from operator_day.connectors.transport import MarketplaceCredentials
from operator_day.db import bind_tenant_scope
from operator_day.domain import (
    ActionResult,
    ActionRisk,
    ConnectedAccount,
    ModuleId,
    Platform,
    Role,
    TaskAction,
    TaskStatus,
    TenantContext,
)
from operator_day.models import (
    Account,
    ActionExecution,
    AuditLog,
    Claim,
    ClaimDeadlinePolicy,
    Feedback,
    HealthCheck,
    PluginManifest,
    Product,
    PvzEmployeeRecord,
    PvzPointRecord,
    Review,
    SelfUpdateRun,
    Task,
    Tenant,
    TokenUsage,
    User,
)
from operator_day.security import TokenCipher, fingerprint_secret


class TaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_tasks(self, ctx: TenantContext, tasks: list[TaskAction]) -> None:
        await bind_tenant_scope(self.session, ctx)
        for task in tasks:
            row = await self.session.get(Task, task.task_id)
            if row is None:
                row = Task(id=task.task_id, tenant_id=ctx.tenant_id)
                self.session.add(row)
            row.module_id = task.module_id.value
            row.title = task.title
            row.short_text = task.short_text
            row.action_label = task.action_label
            row.risk = task.risk.value
            row.status = task.status.value
            row.priority = task.priority
            row.score = task.score
            row.money_effect = task.money_effect
            row.urgency = task.urgency
            row.confidence = task.confidence
            row.deadline_at = task.deadline_at
            row.payload = task.payload
        await self.session.commit()

    async def get_task(self, ctx: TenantContext, task_id: str) -> TaskAction | None:
        await bind_tenant_scope(self.session, ctx)
        row = await self.session.get(Task, task_id)
        if row is None or row.tenant_id != ctx.tenant_id:
            return None
        return self._to_action(row)

    async def list_tasks(self, ctx: TenantContext, *, limit: int = 20) -> list[TaskAction]:
        await bind_tenant_scope(self.session, ctx)
        query = (
            select(Task)
            .where(Task.tenant_id == ctx.tenant_id)
            .order_by(Task.score.desc(), Task.priority.desc(), Task.created_at.desc())
            .limit(limit)
        )
        rows = (await self.session.execute(query)).scalars().all()
        return [self._to_action(row) for row in rows]

    async def get_execution(
        self, ctx: TenantContext, task_id: str, idempotency_key: str
    ) -> ActionResult | None:
        await bind_tenant_scope(self.session, ctx)
        query = select(ActionExecution).where(
            ActionExecution.tenant_id == ctx.tenant_id,
            ActionExecution.task_id == task_id,
            ActionExecution.idempotency_key == idempotency_key,
        )
        row = (await self.session.execute(query)).scalar_one_or_none()
        if row is None:
            return None
        payload = row.result
        return ActionResult(
            task_id=str(payload["task_id"]),
            status=TaskStatus(payload["status"]),
            user_text=str(payload["user_text"]),
            audit_event=dict(payload["audit_event"]),
        )

    async def save_result(
        self,
        ctx: TenantContext,
        task: TaskAction,
        result: ActionResult,
        *,
        idempotency_key: str | None = None,
    ) -> None:
        await bind_tenant_scope(self.session, ctx)
        if idempotency_key and await self.get_execution(ctx, task.task_id, idempotency_key):
            return
        row = await self.session.get(Task, task.task_id)
        if row is not None and row.tenant_id == ctx.tenant_id:
            row.status = result.status.value
        if idempotency_key:
            self.session.add(
                ActionExecution(
                    tenant_id=ctx.tenant_id,
                    task_id=task.task_id,
                    idempotency_key=idempotency_key,
                    status=result.status.value,
                    result={
                        "task_id": result.task_id,
                        "status": result.status.value,
                        "user_text": result.user_text,
                        "audit_event": result.audit_event,
                    },
                )
            )
        if "llm_tokens_estimate" in result.audit_event:
            self.session.add(
                TokenUsage(
                    tenant_id=ctx.tenant_id,
                    product_id=str(result.audit_event.get("review_id", "")),
                    source=str(result.audit_event.get("module", "llm")),
                    payload={
                        "task_id": task.task_id,
                        "model": result.audit_event.get("llm_model", ""),
                        "tokens": int(result.audit_event.get("llm_tokens_estimate") or 0),
                        "used_fallback": bool(result.audit_event.get("llm_used_fallback")),
                    },
                )
            )
        self.session.add(
            AuditLog(
                tenant_id=ctx.tenant_id,
                user_id=ctx.user_id,
                action=str(result.audit_event.get("action", "task_confirmed")),
                before_after=result.audit_event,
            )
        )
        await self.session.commit()

    async def save_feedback(
        self, ctx: TenantContext, task_id: str, score: int, comment: str = ""
    ) -> None:
        await bind_tenant_scope(self.session, ctx)
        self.session.add(
            Feedback(
                tenant_id=ctx.tenant_id,
                task_id=task_id,
                score=score,
                comment=comment,
            )
        )
        await self.session.commit()

    @staticmethod
    def _to_action(row: Task) -> TaskAction:
        return TaskAction(
            module_id=ModuleId(row.module_id),
            title=row.title,
            short_text=row.short_text,
            action_label=row.action_label,
            payload=row.payload,
            priority=row.priority,
            risk=ActionRisk(row.risk),
            money_effect=row.money_effect,
            urgency=row.urgency,
            confidence=row.confidence,
            deadline_at=row.deadline_at,
            score=row.score,
            task_id=row.id,
            status=TaskStatus(row.status),
        )


class AccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._cipher = TokenCipher(get_settings().token_encryption_key)

    async def connect_account(
        self,
        ctx: TenantContext,
        *,
        platform: str,
        title: str,
        secret: str,
        metadata: dict,
    ) -> ConnectedAccount:
        await bind_tenant_scope(self.session, ctx)
        platform_value = Platform(platform)
        row = Account(
            tenant_id=ctx.tenant_id,
            platform=platform_value.value,
            title=title,
            token_enc=self._cipher.encrypt(secret),
            status="ready_for_validation",
            token_fingerprint=fingerprint_secret(secret),
            payload=metadata,
        )
        self.session.add(row)
        self.session.add(
            AuditLog(
                tenant_id=ctx.tenant_id,
                user_id=ctx.user_id,
                action="account_connected",
                before_after={
                    "account_id": row.id,
                    "platform": platform_value.value,
                    "token_fingerprint": row.token_fingerprint,
                },
            )
        )
        await self.session.commit()
        return self._to_connected(row)

    async def list_accounts(self, ctx: TenantContext) -> list[ConnectedAccount]:
        await bind_tenant_scope(self.session, ctx)
        rows = (
            await self.session.execute(
                select(Account).where(Account.tenant_id == ctx.tenant_id).order_by(Account.platform)
            )
        ).scalars()
        return [self._to_connected(row) for row in rows]

    async def credentials_for_account(
        self,
        ctx: TenantContext,
        account_id: str,
    ) -> MarketplaceCredentials:
        await bind_tenant_scope(self.session, ctx)
        row = await self.session.get(Account, account_id)
        if row is None or row.tenant_id != ctx.tenant_id:
            raise KeyError(account_id)
        payload = row.payload or {}
        return MarketplaceCredentials(
            platform=row.platform,
            api_key=self._cipher.decrypt(row.token_enc),
            client_id=str(payload.get("client_id") or ""),
            metadata=dict(payload),
        )

    async def mark_account_validated(
        self,
        ctx: TenantContext,
        *,
        account_id: str,
        source: str,
        operation_id: str,
    ) -> None:
        await bind_tenant_scope(self.session, ctx)
        row = await self.session.get(Account, account_id)
        if row is None or row.tenant_id != ctx.tenant_id:
            raise KeyError(account_id)
        payload = dict(row.payload or {})
        payload["last_validation"] = {
            "source": source,
            "operation_id": operation_id,
        }
        row.payload = payload
        row.status = "validated"
        self.session.add(
            AuditLog(
                tenant_id=ctx.tenant_id,
                user_id=ctx.user_id,
                action="account_validated",
                before_after={
                    "account_id": account_id,
                    "platform": row.platform,
                    "source": source,
                    "operation_id": operation_id,
                    "token_fingerprint": row.token_fingerprint,
                },
            )
        )
        await self.session.commit()

    @staticmethod
    def _to_connected(row: Account) -> ConnectedAccount:
        platform = Platform(row.platform)
        payload = row.payload or {}
        capabilities = _capabilities_for(platform, payload)
        return ConnectedAccount(
            account_id=row.id,
            platform=platform,
            title=row.title or platform.value.upper(),
            status=row.status,
            token_fingerprint=row.token_fingerprint,
            capabilities=capabilities,
            limitations=tuple(
                "Точные лимиты и сроки проверяются по официальному кабинету перед записью"
                for value in capabilities.values()
                if value == "needs_api_verification"
            ),
        )


def _capabilities_for(platform: Platform, payload: dict) -> dict[str, str]:
    if platform == Platform.OZON:
        ads_ready = bool(payload.get("performance_client_id")) and bool(
            payload.get("performance_client_secret")
        )
        return {
            "catalog": "ready",
            "reviews": "ready",
            "finance": "ready",
            "ads": "ready" if ads_ready else "needs_credentials",
            "claims": "needs_api_verification",
        }
    if platform == Platform.WB:
        return {
            "catalog": "ready",
            "reviews": "ready",
            "finance": "ready",
            "ads": "needs_api_verification",
            "claims": "needs_api_verification",
        }
    if platform == Platform.YANDEX:
        campaign_ready = bool(payload.get("campaign_id"))
        return {
            "catalog": "ready" if campaign_ready else "needs_credentials",
            "reviews": "needs_api_verification",
            "finance": "ready",
            "ads": "needs_api_verification",
            "claims": "needs_api_verification",
        }
    return {"pvz": "ready"}


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def context_for_telegram(self, tg_id: str, name: str = "") -> TenantContext:
        provisional = TenantContext(tenant_id=f"tg-{tg_id}", user_id=tg_id, role=Role.OWNER)
        await bind_tenant_scope(self.session, provisional)
        row = (
            await self.session.execute(select(User).where(User.tg_id == tg_id).limit(1))
        ).scalar_one_or_none()
        if row is not None:
            return TenantContext(tenant_id=row.tenant_id, user_id=row.id, role=Role(row.role))

        tenant = Tenant(id=f"tg-{tg_id}", title=name or f"Telegram {tg_id}", plan="pilot")
        user = User(
            tenant_id=tenant.id,
            tg_id=tg_id,
            role=Role.OWNER.value,
            name=name,
        )
        self.session.add(tenant)
        self.session.add(user)
        await self.session.commit()
        return TenantContext(tenant_id=tenant.id, user_id=user.id, role=Role.OWNER)


class ClaimPolicyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_deadline_policy(
        self,
        ctx: TenantContext,
        *,
        platform: str,
        claim_type: str,
        days: int,
        source_url: str,
        note: str = "",
    ) -> ClaimDeadlinePolicy:
        await bind_tenant_scope(self.session, ctx)
        row = ClaimDeadlinePolicy(
            tenant_id=ctx.tenant_id,
            platform=platform,
            claim_type=claim_type,
            days=days,
            source_url=source_url,
            note=note,
        )
        self.session.add(row)
        self.session.add(
            AuditLog(
                tenant_id=ctx.tenant_id,
                user_id=ctx.user_id,
                action="claim_deadline_policy_saved",
                before_after={
                    "platform": platform,
                    "claim_type": claim_type,
                    "days": days,
                    "source_url": source_url,
                },
            )
        )
        await self.session.commit()
        return row

    async def list_deadline_policies(self, ctx: TenantContext) -> list[ClaimDeadlinePolicy]:
        await bind_tenant_scope(self.session, ctx)
        rows = (
            await self.session.execute(
                select(ClaimDeadlinePolicy).where(
                    ClaimDeadlinePolicy.tenant_id == ctx.tenant_id
                )
            )
        ).scalars()
        return list(rows)


class ClaimRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def import_claim_candidates(
        self,
        ctx: TenantContext,
        *,
        rows: list[dict],
    ) -> int:
        await bind_tenant_scope(self.session, ctx)
        count = 0
        for item in rows:
            platform = Platform(str(item.get("platform")))
            sku = str(item.get("sku") or item.get("product_id") or "")
            if not sku:
                continue
            claim_id = str(item.get("claim_id") or "")
            existing = await self.session.get(Claim, claim_id) if claim_id else None
            if existing is not None and existing.tenant_id != ctx.tenant_id:
                raise KeyError(claim_id)
            row = existing or Claim(tenant_id=ctx.tenant_id)
            if existing is None and claim_id:
                row.id = claim_id
            row.product_id = sku
            row.source = platform.value
            row.payload = {
                "claim_type": str(item.get("claim_type") or "lost_or_damaged"),
                "amount": float(item.get("amount") or 0),
                "reason": str(item.get("reason") or ""),
                "evidence": list(item.get("evidence") or []),
                "discovered_at": _iso_datetime(item.get("discovered_at")),
                "source": str(item.get("source") or "manual"),
                "status": str(item.get("status") or "open"),
            }
            if existing is None:
                self.session.add(row)
            count += 1
        self.session.add(
            AuditLog(
                tenant_id=ctx.tenant_id,
                user_id=ctx.user_id,
                action="claim_candidates_imported",
                before_after={"count": count},
            )
        )
        await self.session.commit()
        return count


class PvzRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def import_points(self, ctx: TenantContext, *, rows: list[dict]) -> int:
        await bind_tenant_scope(self.session, ctx)
        count = 0
        employee_count = 0
        for item in rows:
            external_point_id = str(item.get("point_id") or "").strip()
            point_id = (
                _scoped_import_id(ctx, "pvz_point", external_point_id)
                if external_point_id
                else str(uuid4())
            )
            point = await self.session.get(PvzPointRecord, point_id) if point_id else None
            if point is not None and point.tenant_id != ctx.tenant_id:
                raise KeyError(point_id)
            if point is None:
                point = PvzPointRecord(tenant_id=ctx.tenant_id)
                point.id = point_id
                self.session.add(point)
            point.title = str(item.get("title") or point.id)
            point.monthly_turnover = float(item.get("monthly_turnover") or 0)
            point.payload = {
                "source": str(item.get("source") or "manual"),
                "external_point_id": external_point_id or point.id,
            }
            count += 1
            employee_count += await self._replace_employees(
                ctx,
                point_id=point.id,
                rows=list(item.get("employees") or []),
            )
        self.session.add(
            AuditLog(
                tenant_id=ctx.tenant_id,
                user_id=ctx.user_id,
                action="pvz_points_imported",
                before_after={"points": count, "employees": employee_count},
            )
        )
        await self.session.commit()
        return count

    async def _replace_employees(
        self,
        ctx: TenantContext,
        *,
        point_id: str,
        rows: list[dict],
    ) -> int:
        existing = (
            await self.session.execute(
                select(PvzEmployeeRecord).where(
                    PvzEmployeeRecord.tenant_id == ctx.tenant_id,
                    PvzEmployeeRecord.point_id == point_id,
                )
            )
        ).scalars().all()
        for row in existing:
            await self.session.delete(row)
        for item in rows:
            external_employee_id = str(item.get("employee_id") or "").strip()
            employee_id = (
                _scoped_import_id(ctx, f"pvz_employee:{point_id}", external_employee_id)
                if external_employee_id
                else str(uuid4())
            )
            employee = PvzEmployeeRecord(
                tenant_id=ctx.tenant_id,
                point_id=point_id,
                name=str(item.get("name") or external_employee_id or "Сотрудник"),
                hourly_rate=float(item.get("hourly_rate") or 0),
                preferred_days=list(item.get("preferred_days") or []),
                payload={
                    "source": str(item.get("source") or "manual"),
                    "external_employee_id": external_employee_id or employee_id,
                },
            )
            employee.id = employee_id
            self.session.add(employee)
        return len(rows)


def _scoped_import_id(ctx: TenantContext, namespace: str, external_id: str) -> str:
    raw = f"{ctx.tenant_id}:{namespace}:{external_id}".encode()
    return f"imp_{sha256(raw).hexdigest()[:32]}"


class ReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def import_reviews(self, ctx: TenantContext, *, rows: list[dict]) -> int:
        await bind_tenant_scope(self.session, ctx)
        count = 0
        for item in rows:
            platform = Platform(str(item.get("platform") or Platform.OZON.value))
            external_review_id = str(item.get("review_id") or "").strip()
            review_id = (
                _scoped_import_id(ctx, f"review:{platform.value}", external_review_id)
                if external_review_id
                else str(uuid4())
            )
            row = await self.session.get(Review, review_id)
            if row is not None and row.tenant_id != ctx.tenant_id:
                raise KeyError(external_review_id or review_id)
            if row is None:
                row = Review(id=review_id, tenant_id=ctx.tenant_id)
                self.session.add(row)
            row.product_id = str(item.get("sku") or "")
            row.source = platform.value
            row.rating = int(item.get("rating") or 5)
            row.text = str(item.get("text") or "")
            row.answer_status = str(item.get("answer_status") or "new")
            row.payload = {
                "source": str(item.get("source") or "manual"),
                "external_review_id": external_review_id or review_id,
                "buyer_question": str(item.get("buyer_question") or ""),
            }
            count += 1
        self.session.add(
            AuditLog(
                tenant_id=ctx.tenant_id,
                user_id=ctx.user_id,
                action="reviews_imported",
                before_after={"reviews": count},
            )
        )
        await self.session.commit()
        return count


class ReadinessRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def has_passed_architecture_gate(self, ctx: TenantContext) -> bool:
        await bind_tenant_scope(self.session, ctx)
        row = (
            await self.session.execute(
                select(AuditLog)
                .where(
                    AuditLog.tenant_id == ctx.tenant_id,
                    AuditLog.action == "architecture_gate_passed",
                )
                .order_by(AuditLog.created_at.desc())
            )
        ).scalars().first()
        return row is not None

    async def record_architecture_gate_passed(
        self,
        ctx: TenantContext,
        *,
        model: str,
        tokens_estimate: int,
    ) -> None:
        await bind_tenant_scope(self.session, ctx)
        self.session.add(
            AuditLog(
                tenant_id=ctx.tenant_id,
                user_id=ctx.user_id,
                action="architecture_gate_passed",
                before_after={"model": model, "tokens_estimate": tokens_estimate},
            )
        )
        await self.session.commit()


class CatalogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_products(
        self,
        ctx: TenantContext,
        *,
        account_id: str,
        source: str,
        rows: list[dict],
    ) -> int:
        await bind_tenant_scope(self.session, ctx)
        if account_id:
            account = await self.session.get(Account, account_id)
            if account is None or account.tenant_id != ctx.tenant_id:
                raise KeyError(account_id)
        count = 0
        for item in rows:
            sku = str(item.get("offer_id") or item.get("sku") or item.get("product_id") or "")
            if not sku:
                continue
            existing = (
                await self.session.execute(
                    select(Product).where(
                        Product.tenant_id == ctx.tenant_id,
                        Product.account_id == account_id,
                        Product.sku == sku,
                    )
                )
            ).scalar_one_or_none()
            title = str(item.get("title") or item.get("name") or sku)
            if existing is None:
                self.session.add(
                    Product(
                        tenant_id=ctx.tenant_id,
                        account_id=account_id,
                        sku=sku,
                        title=title,
                        category=source,
                        price=float(item.get("price") or 0),
                        cost=float(item.get("cost") or 0),
                    )
                )
            else:
                existing.title = title
                existing.category = source
                existing.price = float(item.get("price") or existing.price or 0)
                existing.cost = float(item.get("cost") or existing.cost or 0)
            count += 1
        self.session.add(
            AuditLog(
                tenant_id=ctx.tenant_id,
                user_id=ctx.user_id,
                action="catalog_products_upserted",
                before_after={
                    "account_id": account_id,
                    "source": source,
                    "count": count,
                },
            )
        )
        await self.session.commit()
        return count


class PluginRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def install_manifest(
        self,
        ctx: TenantContext,
        *,
        manifest: dict,
        activate: bool = False,
    ) -> PluginManifest:
        await bind_tenant_scope(self.session, ctx)
        plugin_id = str(manifest["id"])
        existing = (
            await self.session.execute(
                select(PluginManifest).where(
                    PluginManifest.tenant_id == ctx.tenant_id,
                    PluginManifest.plugin_id == plugin_id,
                )
            )
        ).scalar_one_or_none()
        row = existing or PluginManifest(tenant_id=ctx.tenant_id, plugin_id=plugin_id)
        row.label = str(manifest["label"])
        row.surface = str(manifest["surface"])
        row.module_id = str(manifest["module_id"])
        row.action = str(manifest["action"])
        row.requires_confirm = 1 if bool(manifest.get("requires_confirm", True)) else 0
        row.schema = dict(manifest.get("input_schema") or {})
        row.payload = dict(manifest)
        row.status = "active" if activate else "draft"
        if existing is None:
            self.session.add(row)
        self.session.add(
            AuditLog(
                tenant_id=ctx.tenant_id,
                user_id=ctx.user_id,
                action="plugin_manifest_installed",
                before_after={
                    "plugin_id": plugin_id,
                    "status": row.status,
                    "surface": row.surface,
                    "module_id": row.module_id,
                },
            )
        )
        await self.session.commit()
        return row

    async def list_manifests(self, ctx: TenantContext) -> list[PluginManifest]:
        await bind_tenant_scope(self.session, ctx)
        rows = (
            await self.session.execute(
                select(PluginManifest)
                .where(PluginManifest.tenant_id == ctx.tenant_id)
                .order_by(PluginManifest.created_at.desc())
            )
        ).scalars()
        return list(rows)


class SelfUpdateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_run(
        self,
        ctx: TenantContext,
        *,
        source: str,
        status: str,
        current_snapshot: str,
        candidate_snapshot: str,
        gates: dict,
        payload: dict,
    ) -> SelfUpdateRun:
        await bind_tenant_scope(self.session, ctx)
        row = SelfUpdateRun(
            tenant_id=ctx.tenant_id,
            source=source,
            status=status,
            current_snapshot=current_snapshot,
            candidate_snapshot=candidate_snapshot,
            gates=gates,
            payload=payload,
        )
        self.session.add(row)
        self.session.add(
            AuditLog(
                tenant_id=ctx.tenant_id,
                user_id=ctx.user_id,
                action="self_update_run_recorded",
                before_after={
                    "run_id": row.id,
                    "source": source,
                    "status": status,
                    "candidate_snapshot": candidate_snapshot,
                    "gates": gates,
                },
            )
        )
        await self.session.commit()
        return row

    async def list_runs(self, ctx: TenantContext, *, limit: int = 20) -> list[SelfUpdateRun]:
        await bind_tenant_scope(self.session, ctx)
        rows = (
            await self.session.execute(
                select(SelfUpdateRun)
                .where(SelfUpdateRun.tenant_id == ctx.tenant_id)
                .order_by(SelfUpdateRun.created_at.desc())
                .limit(limit)
            )
        ).scalars()
        return list(rows)


class HealthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(
        self,
        ctx: TenantContext,
        *,
        component: str,
        status: str,
        payload: dict,
    ) -> None:
        await bind_tenant_scope(self.session, ctx)
        self.session.add(
            HealthCheck(
                tenant_id=ctx.tenant_id,
                component=component,
                status=status,
                payload=payload,
            )
        )
        await self.session.commit()


def _iso_datetime(value) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value or "")
