from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from operator_day.claim_deadlines import default_claim_deadline_rules
from operator_day.config import get_settings
from operator_day.connectors.base import ConnectorHealth, MarketplaceClient
from operator_day.connectors.transport import MarketplaceCredentials, MarketplaceTransport
from operator_day.db import bind_tenant_scope
from operator_day.domain import (
    ClaimCandidate,
    ClaimDeadlineRule,
    Platform,
    ProductSnapshot,
    PvzEmployee,
    PvzPoint,
    ReviewSnapshot,
    TenantContext,
)
from operator_day.models import (
    Account,
    AlertRecord,
    CardAsset,
    CardVariant,
    CashOperation,
    Claim,
    ClaimDeadlinePolicy,
    ClaimItem,
    CogsBatch,
    ContentBlock,
    DemandTrend,
    EvalRun,
    HealthCheck,
    IncidentRecord,
    KnowledgeProposal,
    Niche,
    Product,
    ProductIdea,
    PvzEmployeeRecord,
    PvzPointRecord,
    PvzShift,
    ReceiptRecord,
    Reconciliation,
    Review,
    RiskSignal,
    RuleChange,
    RuleVersion,
    Sale,
    SeoDraft,
    SourceChange,
    Stock,
    StudioBuild,
    StudioSpec,
    WarehouseDistribution,
    WhitehatTip,
)
from operator_day.repositories import AccountRepository


class ReplayMarketplaceClient(MarketplaceClient):
    def __init__(self, platform: Platform) -> None:
        self.platform = platform

    async def validate_capabilities(self) -> ConnectorHealth:
        return ConnectorHealth(
            platform=self.platform,
            mode="replay",
            capabilities={
                "catalog": "ready",
                "reviews": "ready",
                "finance": "replay",
                "ads": "replay",
                "claims": "replay",
            },
            limitations=("live API writes are disabled in replay mode",),
        )

    async def list_products(self) -> list[ProductSnapshot]:
        if self.platform == Platform.WB:
            return [
                ProductSnapshot(
                    Platform.WB, "WB-1001", "Органайзер для кухни", 1290, 7, 720, 0.23, 4.7
                ),
                ProductSnapshot(
                    Platform.WB, "WB-1002", "Термокружка 500 мл", 890, 2, 610, 0.28, 4.2
                ),
            ]
        if self.platform == Platform.OZON:
            return [
                ProductSnapshot(
                    Platform.OZON, "OZ-501", "Кабель USB-C 2 м", 390, 140, 180, 0.31, 4.8
                ),
                ProductSnapshot(
                    Platform.OZON, "OZ-502", "Набор контейнеров", 1590, 11, 1040, 0.34, 4.1
                ),
            ]
        return [
            ProductSnapshot(
                Platform.YANDEX,
                "YM-22",
                "Щетка для обуви",
                490,
                4,
                260,
                0.22,
                4.5,
                data_sources={"business_id": "business-123"},
            ),
        ]

    async def list_reviews(self) -> list[ReviewSnapshot]:
        if self.platform == Platform.WB:
            return [
                ReviewSnapshot(
                    Platform.WB,
                    "wb-review-1",
                    "WB-1001",
                    5,
                    "Все пришло быстро, органайзер удобный.",
                ),
                ReviewSnapshot(
                    Platform.WB,
                    "wb-review-2",
                    "WB-1002",
                    2,
                    "Крышка протекает, хочу вернуть.",
                ),
            ]
        if self.platform == Platform.OZON:
            return [
                ReviewSnapshot(
                    Platform.OZON,
                    "oz-question-1",
                    "OZ-501",
                    5,
                    "Покупатель спрашивает про гарантию.",
                    buyer_question="Подойдет для быстрой зарядки?",
                )
            ]
        return []

    async def send_review_answer(self, review_id: str, answer: str) -> dict[str, str]:
        return {"mode": "replay", "review_id": review_id, "status": "accepted", "answer": answer}


class ReplayHub:
    def __init__(self) -> None:
        self.clients = [
            ReplayMarketplaceClient(Platform.WB),
            ReplayMarketplaceClient(Platform.OZON),
            ReplayMarketplaceClient(Platform.YANDEX),
        ]

    async def products(self) -> list[ProductSnapshot]:
        rows: list[ProductSnapshot] = []
        for client in self.clients:
            rows.extend(await client.list_products())
        return rows

    async def reviews(self) -> list[ReviewSnapshot]:
        rows: list[ReviewSnapshot] = []
        for client in self.clients:
            rows.extend(await client.list_reviews())
        return rows

    async def claim_candidates(self) -> list[ClaimCandidate]:
        return [
            ClaimCandidate(
                platform=Platform.OZON,
                claim_id="pilot-lost-1",
                claim_type="lost_or_damaged",
                sku="OZ-501",
                amount=12400,
                reason="Расхождение по складу: товар отгружен, но не отражен в компенсации.",
                evidence=("отгрузка", "остатки", "финотчет"),
                discovered_at=datetime.now(UTC) - timedelta(days=1),
                source="pilot-data",
            )
        ]

    async def claim_deadline_policies(self) -> list[ClaimDeadlineRule]:
        return list(default_claim_deadline_rules())

    async def pvz_points(self) -> list[PvzPoint]:
        return [
            PvzPoint(
                point_id="pilot-pvz-1",
                title="ПВЗ пилот",
                monthly_turnover=1_800_000,
                employees=(
                    PvzEmployee("pilot-anna", "Анна", 220),
                    PvzEmployee("pilot-igor", "Игорь", 220),
                ),
            )
        ]

    async def capabilities(self) -> list[ConnectorHealth]:
        return [await client.validate_capabilities() for client in self.clients]

    async def operational_records(self, kind: str) -> list[dict[str, Any]]:
        return _fallback_operational_records(kind)

    async def send_review_answer(self, review_id: str, answer: str) -> dict[str, str]:
        for client in self.clients:
            reviews = await client.list_reviews()
            if any(review.review_id == review_id for review in reviews):
                return await client.send_review_answer(review_id, answer)
        return {"mode": "replay", "review_id": review_id, "status": "not_found"}

    async def execute_marketplace_operation(
        self,
        operation_id: str,
        payload: dict[str, Any],
        *,
        platform: Platform,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        credentials = MarketplaceCredentials(platform=platform.value, api_key="")
        planned = await MarketplaceTransport(credentials).call_operation(
            operation_id,
            payload,
            dry_run=True,
            idempotency_key=idempotency_key,
        )
        return {
            "mode": "schema_dry_run",
            "status": "planned",
            "live": False,
            "account_id": None,
            "planned_operation": planned,
        }

    async def record_operator_artifact(
        self,
        ctx: TenantContext,
        task_payload: dict[str, Any],
        *,
        module_id: str,
        task_id: str,
    ) -> dict[str, Any]:
        return {
            "mode": "replay",
            "status": "planned",
            "live": False,
            "artifact_type": str(task_payload.get("artifact_type") or "operator_plan"),
            "task_id": task_id,
            "module_id": module_id,
        }


class DatabaseReplayHub(ReplayHub):
    def __init__(self, session: AsyncSession, ctx: TenantContext) -> None:
        super().__init__()
        self.session = session
        self.ctx = ctx

    async def products(self) -> list[ProductSnapshot]:
        await bind_tenant_scope(self.session, self.ctx)
        product_rows = (
            await self.session.execute(
                select(Product, Account.platform)
                .join(Account, Product.account_id == Account.id, isouter=True)
                .where(Product.tenant_id == self.ctx.tenant_id)
                .order_by(Product.sku)
            )
        ).all()
        if not product_rows:
            return await super().products() if _allow_demo_fixtures() else []
        products = [row[0] for row in product_rows]
        product_ids = [row.id for row in products]
        stock_rows = (
            await self.session.execute(
                select(Stock).where(
                    Stock.tenant_id == self.ctx.tenant_id,
                    Stock.product_id.in_(product_ids),
                )
            )
        ).scalars().all()
        stocks_by_product: dict[str, int] = {}
        for row in stock_rows:
            stocks_by_product[row.product_id] = (
                stocks_by_product.get(row.product_id, 0) + row.quantity
            )
        review_rows = (
            await self.session.execute(
                select(Review).where(Review.tenant_id == self.ctx.tenant_id)
            )
        ).scalars().all()
        ratings_by_sku: dict[str, list[int]] = {}
        for row in review_rows:
            ratings_by_sku.setdefault(row.product_id, []).append(row.rating)
        sale_rows = (
            await self.session.execute(
                select(Sale).where(Sale.tenant_id == self.ctx.tenant_id)
            )
        ).scalars().all()
        daily_sales_by_sku: dict[str, float] = {}
        for sku, rows in _group_sales_by_sku(sale_rows).items():
            first_sale = min(_aware_datetime(row.sold_at) for row in rows)
            span_days = max(1, min(30, (datetime.now(UTC) - first_sale).days + 1))
            daily_sales_by_sku[sku] = round(sum(row.quantity for row in rows) / span_days, 2)
        return [
            ProductSnapshot(
                platform=_platform_from_category(account_platform or row.category),
                sku=row.sku,
                name=row.title,
                price=row.price,
                stock=stocks_by_product.get(row.id),
                cost=row.cost,
                commission_rate=float(row.commission_rate or 0),
                rating=_rating_for_product(row, ratings_by_sku),
                daily_sales=daily_sales_by_sku.get(row.sku),
                data_sources=_product_data_sources(
                    row,
                    stocks_by_product,
                    ratings_by_sku,
                    daily_sales_by_sku,
                ),
            )
            for row, account_platform in product_rows
        ]

    async def reviews(self) -> list[ReviewSnapshot]:
        await bind_tenant_scope(self.session, self.ctx)
        rows = (
            await self.session.execute(
                select(Review).where(Review.tenant_id == self.ctx.tenant_id).order_by(Review.id)
            )
        ).scalars().all()
        if not rows:
            return await super().reviews() if _allow_demo_fixtures() else []
        return [
            ReviewSnapshot(
                platform=_platform_from_category(row.source),
                review_id=str((row.payload or {}).get("external_review_id") or row.id),
                sku=row.product_id,
                rating=row.rating,
                text=row.text,
                buyer_question=str((row.payload or {}).get("buyer_question") or "") or None,
            )
            for row in rows
        ]

    async def claim_candidates(self) -> list[ClaimCandidate]:
        await bind_tenant_scope(self.session, self.ctx)
        rows = (
            await self.session.execute(
                select(Claim).where(Claim.tenant_id == self.ctx.tenant_id).order_by(Claim.id)
            )
        ).scalars().all()
        if not rows:
            return await super().claim_candidates() if _allow_demo_fixtures() else []
        return [_claim_candidate_from_row(row) for row in rows]

    async def claim_deadline_policies(self) -> list[ClaimDeadlineRule]:
        await bind_tenant_scope(self.session, self.ctx)
        rows = (
            await self.session.execute(
                select(ClaimDeadlinePolicy).where(
                    ClaimDeadlinePolicy.tenant_id == self.ctx.tenant_id
                )
            )
        ).scalars().all()
        policies = [
            ClaimDeadlineRule(
                platform=_platform_from_category(row.platform),
                claim_type=row.claim_type,
                days=row.days,
                source_url=row.source_url,
                note=row.note,
            )
            for row in rows
        ]
        seen = {(policy.platform, policy.claim_type) for policy in policies}
        policies.extend(
            policy
            for policy in default_claim_deadline_rules()
            if (policy.platform, policy.claim_type) not in seen
        )
        return policies

    async def pvz_points(self) -> list[PvzPoint]:
        await bind_tenant_scope(self.session, self.ctx)
        point_rows = (
            await self.session.execute(
                select(PvzPointRecord)
                .where(PvzPointRecord.tenant_id == self.ctx.tenant_id)
                .order_by(PvzPointRecord.title)
            )
        ).scalars().all()
        if not point_rows:
            return await super().pvz_points() if _allow_demo_fixtures() else []
        employee_rows = (
            await self.session.execute(
                select(PvzEmployeeRecord).where(
                    PvzEmployeeRecord.tenant_id == self.ctx.tenant_id
                )
            )
        ).scalars().all()
        employees_by_point: dict[str, list[PvzEmployee]] = {}
        for row in employee_rows:
            payload = row.payload or {}
            employees_by_point.setdefault(row.point_id, []).append(
                PvzEmployee(
                    employee_id=str(payload.get("external_employee_id") or row.id),
                    name=row.name,
                    hourly_rate=row.hourly_rate,
                    preferred_days=tuple(int(day) for day in (row.preferred_days or [])),
                )
            )
        return [
            PvzPoint(
                point_id=str((row.payload or {}).get("external_point_id") or row.id),
                title=row.title,
                monthly_turnover=row.monthly_turnover,
                employees=tuple(employees_by_point.get(row.id, [])),
            )
            for row in point_rows
        ]

    async def operational_records(self, kind: str) -> list[dict[str, Any]]:
        await bind_tenant_scope(self.session, self.ctx)
        model = _OPERATIONAL_MODELS.get(kind)
        if model is None:
            return []
        rows = (
            await self.session.execute(
                select(model)
                .where(model.tenant_id == self.ctx.tenant_id)
                .order_by(model.created_at.desc())
                .limit(50)
            )
        ).scalars().all()
        if not rows:
            return _fallback_operational_records(kind) if _allow_demo_fixtures() else []
        result: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row.payload or {})
            payload.setdefault("id", row.id)
            payload.setdefault("sku", row.product_id)
            payload.setdefault("source", row.source)
            payload.setdefault("created_at", row.created_at.isoformat())
            result.append(payload)
        return result

    async def send_review_answer(self, review_id: str, answer: str) -> dict[str, str]:
        await bind_tenant_scope(self.session, self.ctx)
        rows = (
            await self.session.execute(
                select(Review).where(Review.tenant_id == self.ctx.tenant_id)
            )
        ).scalars().all()
        for row in rows:
            payload = row.payload or {}
            if row.id == review_id or payload.get("external_review_id") == review_id:
                row.answer_status = "prepared"
                row.payload = {**payload, "last_answer": answer}
                await self.session.commit()
                break
        return {
            "mode": "database",
            "review_id": review_id,
            "status": "prepared",
            "answer": answer,
        }

    async def execute_marketplace_operation(
        self,
        operation_id: str,
        payload: dict[str, Any],
        *,
        platform: Platform,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        await bind_tenant_scope(self.session, self.ctx)
        account = (
            await self.session.execute(
                select(Account)
                .where(Account.tenant_id == self.ctx.tenant_id, Account.platform == platform.value)
                .order_by(Account.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        live_requested = get_settings().marketplace_write_mode == "live"
        if account is None:
            return await super().execute_marketplace_operation(
                operation_id,
                payload,
                platform=platform,
                idempotency_key=idempotency_key,
            )
        account_repo = AccountRepository(self.session)
        credentials = await account_repo.credentials_for_account(self.ctx, account.id)
        operation_platform = MarketplaceTransport(credentials).operations[operation_id].platform
        if operation_platform == "ozon_performance":
            credentials = await account_repo.performance_credentials_for_account(
                self.ctx,
                account.id,
            )
        transport = MarketplaceTransport(credentials)
        operation = transport.operations[operation_id]
        compatible_live_platforms = {platform.value}
        if platform == Platform.OZON:
            compatible_live_platforms.add("ozon_performance")
        if platform == Platform.YANDEX:
            compatible_live_platforms.add("yandex_market")
        capability_name = _capability_for_operation(operation_id)
        connected = AccountRepository._to_connected(account)
        capability_status = connected.capabilities.get(capability_name, "needs_api_verification")
        write_capability_status = _write_capability_status(account, capability_name)
        live_allowed = (
            live_requested
            and account.status == "validated"
            and operation.platform in compatible_live_platforms
            and capability_status == "ready"
            and write_capability_status == "ready"
        )
        transport_result = await transport.call_operation(
            operation_id,
            payload,
            confirm_write=live_allowed,
            dry_run=not live_allowed,
            idempotency_key=idempotency_key
            or f"{self.ctx.tenant_id}:{account.id}:{operation_id}",
        )
        return {
            "mode": "live" if live_allowed else "tenant_dry_run",
            "status": "executed" if live_allowed else "planned",
            "live": live_allowed,
            "account_id": account.id,
            "write_capability": capability_name,
            "write_capability_status": capability_status,
            "write_scope_status": write_capability_status,
            "planned_operation": None if live_allowed else transport_result,
            "response": transport_result if live_allowed else None,
        }

    async def record_operator_artifact(
        self,
        ctx: TenantContext,
        task_payload: dict[str, Any],
        *,
        module_id: str,
        task_id: str,
    ) -> dict[str, Any]:
        await bind_tenant_scope(self.session, self.ctx)
        artifact_type = str(task_payload.get("artifact_type") or "operator_plan")
        model = _ARTIFACT_MODELS.get(artifact_type)
        payload = {
            "task_id": task_id,
            "module_id": module_id,
            "status": "recorded",
            "source": "operator_day",
            "payload": task_payload,
        }
        if model is HealthCheck or model is None:
            row = HealthCheck(
                tenant_id=ctx.tenant_id,
                component=module_id,
                status="recorded",
                payload={**payload, "artifact_type": artifact_type},
            )
        else:
            row = model(
                tenant_id=ctx.tenant_id,
                product_id=str(task_payload.get("sku") or ""),
                source=module_id,
                payload=payload,
            )
        self.session.add(row)
        await self.session.commit()
        return {
            "mode": "database",
            "status": "recorded",
            "live": False,
            "artifact_type": artifact_type,
            "artifact_id": row.id,
            "task_id": task_id,
            "module_id": module_id,
        }


def _platform_from_category(value: str) -> Platform:
    try:
        return Platform(value)
    except ValueError:
        return Platform.OZON


def _allow_demo_fixtures() -> bool:
    settings = get_settings()
    return settings.is_local_env() and settings.allow_demo_fixtures


def _capability_for_operation(operation_id: str) -> str:
    if "Review" in operation_id or "Questions" in operation_id:
        return "reviews"
    if "Campaign" in operation_id or "Bids" in operation_id or "Promotion" in operation_id:
        return "ads"
    if "Price" in operation_id or "Product" in operation_id or "Content" in operation_id:
        return "catalog"
    return "catalog"


def _write_capability_status(account: Account, capability_name: str) -> str:
    payload = account.payload or {}
    write_capabilities = payload.get("write_capabilities") or payload.get("writeCapabilities") or {}
    if not isinstance(write_capabilities, dict):
        return "needs_write_verification"
    return str(write_capabilities.get(capability_name) or "needs_write_verification")


def _group_sales_by_sku(rows: list[Sale]) -> dict[str, list[Sale]]:
    grouped: dict[str, list[Sale]] = {}
    for row in rows:
        grouped.setdefault(row.sku, []).append(row)
    return grouped


def _int_from_payload(payload: dict | None, key: str) -> int:
    if not isinstance(payload, dict):
        return 0
    try:
        return max(0, int(float(payload.get(key) or payload.get("quantity") or 0)))
    except (TypeError, ValueError):
        return 0


def _rating_for_product(row: Product, ratings_by_sku: dict[str, list[int]]) -> float:
    if row.rating:
        return float(row.rating)
    ratings = ratings_by_sku.get(row.sku) or []
    if not ratings:
        return 0
    return round(sum(ratings) / len(ratings), 2)


def _product_data_sources(
    row: Product,
    stocks_by_product: dict[str, int],
    ratings_by_sku: dict[str, list[int]],
    daily_sales_by_sku: dict[str, float],
) -> dict[str, str]:
    payload = row.payload or {}
    business_id = str(payload.get("business_id") or payload.get("businessId") or "")
    return {
        "price": "catalog",
        "cost": "catalog" if row.cost else "missing",
        "commission": "catalog" if row.commission_rate else "missing",
        "rating": (
            "catalog" if row.rating else "reviews" if row.sku in ratings_by_sku else "missing"
        ),
        "stock": "stocks" if row.id in stocks_by_product else "missing",
        "daily_sales": "sales" if row.sku in daily_sales_by_sku else "heuristic",
        "business_id": business_id,
    }


_ARTIFACT_MODELS = {
    "catalog_summary": HealthCheck,
    "unit_economics": CogsBatch,
    "seo_draft": SeoDraft,
    "supply_plan": WarehouseDistribution,
    "competitor_watch": RiskSignal,
    "finance_reconciliation": Reconciliation,
    "antifraud_case": RiskSignal,
    "forecast_plan": WarehouseDistribution,
    "pvz_shift_plan": PvzShift,
    "rules_watch": WhitehatTip,
    "rule_recalculation": RuleVersion,
    "accounting_export": ReceiptRecord,
    "billing_note": HealthCheck,
    "studio_build": StudioBuild,
    "supervisor_check": HealthCheck,
    "learning_note": HealthCheck,
    "learning_update": EvalRun,
    "radar_note": WhitehatTip,
    "knowledge_proposal": KnowledgeProposal,
    "claim_draft": ClaimItem,
    "niche_snapshot": Niche,
    "demand_trend": DemandTrend,
    "product_idea": ProductIdea,
    "content_brief": ContentBlock,
    "card_asset": CardAsset,
    "card_variant": CardVariant,
}

_OPERATIONAL_MODELS = {
    "rule_changes": RuleChange,
    "rule_versions": RuleVersion,
    "cash_ops": CashOperation,
    "receipts": ReceiptRecord,
    "studio_specs": StudioSpec,
    "studio_builds": StudioBuild,
    "incidents": IncidentRecord,
    "alerts": AlertRecord,
    "eval_runs": EvalRun,
    "source_changes": SourceChange,
    "knowledge_proposals": KnowledgeProposal,
}


def _fallback_operational_records(kind: str) -> list[dict[str, Any]]:
    now = datetime.now(UTC).isoformat()
    fallback: dict[str, list[dict[str, Any]]] = {
        "rule_changes": [
            {
                "id": "pilot-rule-tariff-1",
                "title": "Изменился тариф хранения",
                "source": "official-rules-radar",
                "source_url": "https://seller.wildberries.ru/help-center",
                "impact": "margin",
                "affected_revenue": 18000,
                "status": "open",
                "created_at": now,
            }
        ],
        "cash_ops": [
            {
                "id": "pilot-cash-1",
                "title": "Операции ПВЗ готовы к выгрузке",
                "source": "pvz-cashbox",
                "amount": 142300,
                "unmatched_amount": 1200,
                "status": "open",
                "created_at": now,
            }
        ],
        "studio_specs": [
            {
                "id": "pilot-studio-1",
                "title": "Пользователь просит кнопку сверки отчета",
                "source": "operator-studio",
                "module_id": "M08_FINANCE",
                "status": "open",
                "created_at": now,
            }
        ],
        "incidents": [
            {
                "id": "pilot-supervisor-1",
                "title": "Проверка лимитов выявила риск возврата",
                "source": "health",
                "risk_type": "return_risk",
                "severity": "high",
                "status": "open",
                "sku": "OZ-501",
                "created_at": now,
            }
        ],
        "alerts": [
            {
                "id": "replay-campaign-risk-1",
                "title": "Похожий на скликивание всплеск",
                "source": "ads-monitor",
                "risk_type": "campaign_risk",
                "severity": "high",
                "status": "open",
                "campaign_id": "campaign-321",
                "created_at": now,
            }
        ],
        "eval_runs": [
            {
                "id": "pilot-eval-1",
                "title": "Проверка качества ответов",
                "source": "feedback-loop",
                "score": 0.82,
                "status": "passed",
                "created_at": now,
            }
        ],
        "source_changes": [
            {
                "id": "pilot-source-1",
                "title": "GitHub: обновлён durable workflow референс",
                "source": "github-radar",
                "source_url": "https://github.com/restatedev/restate",
                "status": "proposal",
                "created_at": now,
            }
        ],
    }
    return list(fallback.get(kind, []))


def _claim_candidate_from_row(row: Claim) -> ClaimCandidate:
    payload = row.payload or {}
    evidence = payload.get("evidence") or ()
    if isinstance(evidence, str):
        evidence = (evidence,)
    return ClaimCandidate(
        platform=_platform_from_category(row.source),
        claim_id=row.id,
        claim_type=str(payload.get("claim_type") or "lost_or_damaged"),
        sku=row.product_id,
        amount=float(payload.get("amount") or 0),
        reason=str(payload.get("reason") or "Найдена сумма к проверке по претензии."),
        evidence=tuple(str(item) for item in evidence),
        discovered_at=_parse_datetime(payload.get("discovered_at")),
        source=str(payload.get("source") or row.source),
    )


def _parse_datetime(value) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            return datetime.now(UTC)
    return datetime.now(UTC)


def _aware_datetime(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
