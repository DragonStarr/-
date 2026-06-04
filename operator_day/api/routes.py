from __future__ import annotations

from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from operator_day.api.context import get_tenant_context, normalize_idempotency_key
from operator_day.api.schemas import (
    AccountIn,
    AccountOut,
    ArchitectureGateOut,
    ArchitectureReviewOut,
    AuthSessionOut,
    CapabilityOut,
    CatalogImportIn,
    CatalogImportOut,
    ClaimDeadlineIn,
    ClaimDeadlineOut,
    ClaimsImportIn,
    ClaimsImportOut,
    ConfirmOut,
    FeedbackIn,
    LlmStatusOut,
    MemoryIn,
    MemoryOut,
    MemorySearchIn,
    OperationalDataImportIn,
    OperationalDataImportOut,
    OperationalDataOut,
    PluginManifestIn,
    PluginManifestOut,
    PvzImportIn,
    PvzImportOut,
    ReviewsImportIn,
    ReviewsImportOut,
    SalesImportIn,
    SalesImportOut,
    SelfUpdateOut,
    SelfUpdatePlanIn,
    SelfUpdateRunIn,
    SyncCatalogIn,
    SyncCatalogOut,
    TaskOut,
    TelegramAuthIn,
    ValidateAccountIn,
    ValidateAccountOut,
    WriteScopeVerificationIn,
    WriteScopeVerificationOut,
)
from operator_day.brain.architecture import ArchitectureReviewService
from operator_day.brain.llm import LlmRouter
from operator_day.brain.orchestrator import MorningOrchestrator
from operator_day.claim_deadlines import (
    OWNER_VERIFICATION_REQUIRED,
    default_claim_deadline_rules,
)
from operator_day.config import get_settings
from operator_day.connectors.live_sync import (
    plan_catalog_sync_for_account,
    sync_catalog_for_account,
    validate_account_for_read_access,
)
from operator_day.connectors.replay import DatabaseReplayHub
from operator_day.connectors.transport import MarketplaceApiError
from operator_day.db import get_session
from operator_day.domain import TenantContext
from operator_day.modules.implementations import ModuleRegistry
from operator_day.plugins.registry import validate_plugin_manifest
from operator_day.policies import (
    ensure_can_confirm,
    ensure_can_connect_account,
    ensure_can_manage_pvz,
)
from operator_day.repositories import (
    AccountRepository,
    CatalogRepository,
    ClaimPolicyRepository,
    ClaimRepository,
    MemoryRepository,
    OperationalRecordRepository,
    PluginRepository,
    PvzRepository,
    ReadinessRepository,
    ReviewRepository,
    SalesRepository,
    SelfUpdateRepository,
    TaskRepository,
    UserRepository,
)
from operator_day.security import (
    AuthError,
    create_session_token,
    telegram_identity_from_init_data,
    verify_telegram_init_data,
)
from operator_day.selfupdate.pipeline import SelfUpdatePipeline
from operator_day.skills_catalog import CORE_MCP_CHECKS, all_operator_capabilities
from operator_day.telemetry.metrics import render_prometheus_metrics

router = APIRouter()
SessionDep = Annotated[AsyncSession, Depends(get_session)]
ContextDep = Annotated[TenantContext, Depends(get_tenant_context)]


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "mode": "bot-miniapp-autonomous"}


@router.post("/api/auth/telegram", response_model=AuthSessionOut)
async def auth_telegram(payload: TelegramAuthIn, session: SessionDep) -> AuthSessionOut:
    settings = get_settings()
    try:
        values = verify_telegram_init_data(
            payload.init_data,
            settings.telegram_bot_token,
            ttl_seconds=settings.telegram_web_app_auth_ttl_seconds,
        )
        tg_id, name = telegram_identity_from_init_data(values)
        ctx = await UserRepository(session).context_for_telegram(tg_id, name)
        token = create_session_token(
            ctx,
            settings.app_session_secret,
            ttl_seconds=settings.app_session_ttl_seconds,
        )
    except AuthError as exc:
        raise HTTPException(status_code=401, detail="Invalid Telegram auth") from exc
    return AuthSessionOut(
        accessToken=token,
        expiresIn=settings.app_session_ttl_seconds,
        tenantId=ctx.tenant_id,
        userId=ctx.user_id,
        role=ctx.role.value,
    )


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> str:
    return render_prometheus_metrics()


@router.get("/api/tasks/morning", response_model=list[TaskOut])
async def morning_tasks(session: SessionDep, ctx: ContextDep, limit: int = 5) -> list[TaskOut]:
    request_orchestrator = MorningOrchestrator(replay=DatabaseReplayHub(session, ctx))
    tasks = await request_orchestrator.morning_top(ctx, limit=limit)
    await TaskRepository(session).save_tasks(ctx, tasks)
    return [_task_out(task) for task in tasks]


@router.get("/api/tasks", response_model=list[TaskOut])
async def list_tasks(session: SessionDep, ctx: ContextDep, limit: int = 20) -> list[TaskOut]:
    return [_task_out(task) for task in await TaskRepository(session).list_tasks(ctx, limit=limit)]


@router.post("/api/tasks/{task_id}/confirm", response_model=ConfirmOut)
async def confirm_task(
    task_id: str,
    session: SessionDep,
    ctx: ContextDep,
    x_idempotency_key: Annotated[str | None, Header(alias="X-Idempotency-Key")] = None,
) -> ConfirmOut:
    repo = TaskRepository(session)
    idempotency_key = normalize_idempotency_key(ctx, task_id, x_idempotency_key)
    existing = await repo.get_execution(ctx, task_id, idempotency_key)
    if existing is not None:
        return _confirm_out(existing)
    task = await repo.get_task(ctx, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Дело не найдено")
    ensure_can_confirm(ctx, task)
    request_orchestrator = MorningOrchestrator(replay=DatabaseReplayHub(session, ctx))
    try:
        result = await request_orchestrator.execute_prepared(ctx, task)
    except (MarketplaceApiError, httpx.HTTPError) as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "Кабинет маркетплейса не принял действие. "
                "Мы ничего не изменили; проверьте доступы и повторите."
            ),
        ) from exc
    await repo.save_result(ctx, task, result, idempotency_key=idempotency_key)
    return _confirm_out(result)


@router.post("/api/feedback")
async def feedback(
    payload: FeedbackIn,
    session: SessionDep,
    ctx: ContextDep,
) -> dict[str, str | int]:
    await TaskRepository(session).save_feedback(
        ctx,
        task_id=payload.task_id,
        score=payload.score,
        comment=payload.comment,
    )
    return {"status": "saved", "taskId": payload.task_id, "score": payload.score}


@router.post("/api/accounts", response_model=AccountOut)
async def connect_account(payload: AccountIn, session: SessionDep, ctx: ContextDep) -> AccountOut:
    ensure_can_connect_account(ctx)
    metadata = {
        "client_id": payload.client_id,
        "performance_client_id": payload.performance_client_id,
        "performance_client_secret": payload.performance_client_secret or "",
        "review_management_subscription": payload.review_management_subscription,
        "campaign_id": payload.campaign_id,
        "business_id": payload.business_id,
    }
    account = await AccountRepository(session).connect_account(
        ctx,
        platform=payload.platform,
        title=payload.title,
        secret=payload.api_key,
        metadata=metadata,
    )
    return _account_out(account)


@router.get("/api/accounts/capabilities", response_model=list[CapabilityOut])
async def account_capabilities(session: SessionDep, ctx: ContextDep) -> list[CapabilityOut]:
    accounts = await AccountRepository(session).list_accounts(ctx)
    return [
        CapabilityOut(
            accountId=account.account_id,
            platform=account.platform.value,
            title=account.title,
            capabilities=account.capabilities,
            limitations=account.limitations,
        )
        for account in accounts
    ]


@router.post("/api/claims/import", response_model=ClaimsImportOut)
async def import_claims(
    payload: ClaimsImportIn,
    session: SessionDep,
    ctx: ContextDep,
) -> ClaimsImportOut:
    ensure_can_connect_account(ctx)
    rows = [claim.model_dump() for claim in payload.claims]
    try:
        count = await ClaimRepository(session).import_claim_candidates(ctx, rows=rows)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Неверная площадка претензии") from exc
    except KeyError as exc:
        raise HTTPException(
            status_code=409,
            detail="Претензия принадлежит другому продавцу",
        ) from exc
    return ClaimsImportOut(count=count)


@router.post("/api/pvz/import", response_model=PvzImportOut)
async def import_pvz(
    payload: PvzImportIn,
    session: SessionDep,
    ctx: ContextDep,
) -> PvzImportOut:
    ensure_can_manage_pvz(ctx)
    rows = [point.model_dump() for point in payload.points]
    try:
        count = await PvzRepository(session).import_points(ctx, rows=rows)
    except KeyError as exc:
        raise HTTPException(status_code=409, detail="ПВЗ принадлежит другому владельцу") from exc
    return PvzImportOut(count=count)


@router.post("/api/reviews/import", response_model=ReviewsImportOut)
async def import_reviews(
    payload: ReviewsImportIn,
    session: SessionDep,
    ctx: ContextDep,
) -> ReviewsImportOut:
    ensure_can_connect_account(ctx)
    rows = [review.model_dump() for review in payload.reviews]
    try:
        count = await ReviewRepository(session).import_reviews(ctx, rows=rows)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Неверная площадка отзыва") from exc
    except KeyError as exc:
        raise HTTPException(status_code=409, detail="Отзыв принадлежит другому продавцу") from exc
    return ReviewsImportOut(count=count)


@router.post("/api/catalog/import", response_model=CatalogImportOut)
async def import_catalog(
    payload: CatalogImportIn,
    session: SessionDep,
    ctx: ContextDep,
) -> CatalogImportOut:
    ensure_can_connect_account(ctx)
    rows = [product.model_dump() for product in payload.products]
    try:
        count = await CatalogRepository(session).upsert_products(
            ctx,
            account_id=payload.account_id,
            source=payload.source,
            rows=rows,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Кабинет не найден") from exc
    return CatalogImportOut(accountId=payload.account_id, source=payload.source, count=count)


@router.post("/api/sales/import", response_model=SalesImportOut)
async def import_sales(
    payload: SalesImportIn,
    session: SessionDep,
    ctx: ContextDep,
) -> SalesImportOut:
    ensure_can_connect_account(ctx)
    rows = [sale.model_dump(by_alias=True) for sale in payload.sales]
    try:
        count = await SalesRepository(session).import_sales(
            ctx,
            account_id=payload.account_id,
            rows=rows,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Неверная площадка продажи") from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Кабинет не найден") from exc
    return SalesImportOut(accountId=payload.account_id, count=count)


@router.post("/api/operational-data/import", response_model=OperationalDataImportOut)
async def import_operational_data(
    payload: OperationalDataImportIn,
    session: SessionDep,
    ctx: ContextDep,
) -> OperationalDataImportOut:
    ensure_can_connect_account(ctx)
    try:
        count = await OperationalRecordRepository(session).import_records(
            ctx,
            kind=payload.kind,
            rows=payload.records,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Неверный тип данных") from exc
    except KeyError as exc:
        raise HTTPException(status_code=409, detail="Запись принадлежит другому продавцу") from exc
    return OperationalDataImportOut(kind=payload.kind, count=count)


@router.get("/api/operational-data/{kind}", response_model=OperationalDataOut)
async def list_operational_data(
    kind: str,
    session: SessionDep,
    ctx: ContextDep,
    limit: int = 50,
) -> OperationalDataOut:
    ensure_can_connect_account(ctx)
    try:
        records = await OperationalRecordRepository(session).list_records(
            ctx,
            kind=kind,
            limit=min(max(limit, 1), 100),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Неверный тип данных") from exc
    return OperationalDataOut(kind=kind, records=records)


@router.post("/api/accounts/{account_id}/sync/catalog", response_model=SyncCatalogOut)
async def sync_catalog(
    account_id: str,
    payload: SyncCatalogIn,
    session: SessionDep,
    ctx: ContextDep,
) -> SyncCatalogOut:
    ensure_can_connect_account(ctx)
    try:
        if payload.dry_run:
            result = await plan_catalog_sync_for_account(session, ctx, account_id)
        else:
            result = await sync_catalog_for_account(session, ctx, account_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Кабинет не найден") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return SyncCatalogOut(
        accountId=result["account_id"],
        source=result["source"],
        dryRun=bool(result.get("dry_run", False)),
        count=int(result["count"]),
        plannedOperation=result.get("planned_operation"),
    )


@router.post("/api/accounts/{account_id}/validate", response_model=ValidateAccountOut)
async def validate_account(
    account_id: str,
    payload: ValidateAccountIn,
    session: SessionDep,
    ctx: ContextDep,
) -> ValidateAccountOut:
    ensure_can_connect_account(ctx)
    try:
        result = await validate_account_for_read_access(
            session,
            ctx,
            account_id,
            dry_run=payload.dry_run,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Кабинет не найден") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ValidateAccountOut(
        accountId=result["account_id"],
        source=result["source"],
        status=result["status"],
        dryRun=bool(result.get("dry_run", False)),
        plannedOperation=result.get("planned_operation"),
    )


@router.post(
    "/api/accounts/{account_id}/write-scopes",
    response_model=WriteScopeVerificationOut,
)
async def verify_account_write_scopes(
    account_id: str,
    payload: WriteScopeVerificationIn,
    session: SessionDep,
    ctx: ContextDep,
) -> WriteScopeVerificationOut:
    ensure_can_connect_account(ctx)
    try:
        scopes = await AccountRepository(session).mark_write_scopes_verified(
            ctx,
            account_id=account_id,
            scopes=payload.scopes,
            source_url=payload.source_url,
            evidence=payload.evidence,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Кабинет не найден") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return WriteScopeVerificationOut(
        accountId=account_id,
        scopes=scopes,
        status="verified",
    )


@router.get("/api/readiness")
async def readiness(session: SessionDep, ctx: ContextDep) -> dict:
    account_repo = AccountRepository(session)
    accounts = await account_repo.list_accounts(ctx)
    write_scope_blockers = await account_repo.missing_write_scope_verifications(ctx)
    claim_policies = await ClaimPolicyRepository(session).list_deadline_policies(ctx)
    gate_passed = await ReadinessRepository(session).has_passed_architecture_gate(ctx)
    blockers: list[str] = []
    mode = "live" if accounts else "safe_test"
    if not accounts:
        blockers.append("real_marketplace_tokens")
    if any(account.status != "validated" for account in accounts):
        blockers.append("marketplace_api_verification")
    if accounts and write_scope_blockers:
        blockers.append("marketplace_write_scope_verification")
    claim_policy_count = len(claim_policies)
    if accounts and claim_policy_count == 0:
        blockers.append("claim_deadline_policies")
    if not gate_passed:
        blockers.append("prod_llm_gate")
    if not get_settings().morning_scheduler_enabled:
        blockers.append("morning_scheduler")
    if not get_settings().self_update_checks_enabled:
        blockers.append("self_update_checks")
    status = "ready_for_live_pilot"
    if "real_marketplace_tokens" in blockers:
        status = "ready_for_safe_pilot"
    elif blockers:
        status = "blocked_for_live_pilot"
    return {
        "status": status,
        "mode": mode,
        "moduleCount": len(ModuleRegistry.default().modules) + 1,
        "skillsAndPlugins": len(all_operator_capabilities()),
        "checksPerAction": len(CORE_MCP_CHECKS),
        "accounts": len(accounts),
        "claimDeadlinePolicies": claim_policy_count,
        "architectureGatePassed": gate_passed,
        "morningSchedulerEnabled": get_settings().morning_scheduler_enabled,
        "selfUpdateChecksEnabled": get_settings().self_update_checks_enabled,
        "writeScopeBlockers": write_scope_blockers,
        "blockers": blockers,
    }


@router.get("/api/brain/architecture-review", response_model=ArchitectureReviewOut)
async def architecture_review(ctx: ContextDep) -> ArchitectureReviewOut:
    ensure_can_connect_account(ctx)
    review = await ArchitectureReviewService(LlmRouter(get_settings())).build_review()
    return ArchitectureReviewOut(
        text=review.text,
        model=review.model,
        usedFallback=review.used_fallback,
        tokensEstimate=review.tokens_estimate,
    )


@router.get("/api/brain/architecture-gate", response_model=ArchitectureGateOut)
async def architecture_gate(
    session: SessionDep,
    ctx: ContextDep,
    live: bool = False,
) -> ArchitectureGateOut:
    ensure_can_connect_account(ctx)
    settings = get_settings()
    force_offline = not (live and settings.llm_smoke_enabled)
    gate = await ArchitectureReviewService(LlmRouter(settings)).build_gate(
        force_offline=force_offline
    )
    if live and gate.verdict == "pass" and not gate.used_fallback:
        await ReadinessRepository(session).record_architecture_gate_passed(
            ctx,
            model=gate.model,
            tokens_estimate=gate.tokens_estimate,
        )
    return ArchitectureGateOut(
        topology=gate.topology,
        verdict=gate.verdict,
        text=gate.text,
        blockers=gate.blockers,
        model=gate.model,
        usedFallback=gate.used_fallback,
        tokensEstimate=gate.tokens_estimate,
    )


@router.get("/api/brain/llm-status", response_model=LlmStatusOut)
async def llm_status(ctx: ContextDep, live: bool = False) -> LlmStatusOut:
    ensure_can_connect_account(ctx)
    settings = get_settings()
    configured = bool(settings.local_llm_base_url) or bool(settings.freemodel_api_key)
    live_check_ran = False
    model_available: bool | None = None
    status = "not_configured"
    if configured:
        status = "configured"
    if live and configured and not settings.llm_smoke_enabled:
        status = "live_disabled"
    if live and configured and settings.llm_smoke_enabled:
        live_check_ran = True
        try:
            router = LlmRouter(settings)
            model_available = await router.probe_model()
            status = "live_ok" if model_available else "model_missing"
        except Exception:
            model_available = False
            status = "live_error"
    return LlmStatusOut(
        configured=configured,
        model=LlmRouter(settings).primary_model,
        primaryProvider=settings.llm_primary_provider,
        primaryModel=settings.local_llm_model,
        externalEnabled=settings.external_llm_enabled,
        smokeEnabled=settings.llm_smoke_enabled,
        liveCheckRequested=live,
        liveCheckRan=live_check_ran,
        modelAvailable=model_available,
        status=status,
    )


@router.get("/api/plugins", response_model=list[PluginManifestOut])
async def list_plugins(session: SessionDep, ctx: ContextDep) -> list[PluginManifestOut]:
    ensure_can_connect_account(ctx)
    rows = await PluginRepository(session).list_manifests(ctx)
    return [_plugin_out(row) for row in rows]


@router.post("/api/plugins", response_model=PluginManifestOut)
async def install_plugin(
    payload: PluginManifestIn,
    session: SessionDep,
    ctx: ContextDep,
) -> PluginManifestOut:
    ensure_can_connect_account(ctx)
    try:
        manifest = validate_plugin_manifest(payload.model_dump(by_alias=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    row = await PluginRepository(session).install_manifest(
        ctx,
        manifest=manifest.model_dump(by_alias=False),
        activate=payload.activate,
    )
    return _plugin_out(row)


@router.post("/api/memory", response_model=MemoryOut)
async def save_memory(payload: MemoryIn, session: SessionDep, ctx: ContextDep) -> MemoryOut:
    ensure_can_connect_account(ctx)
    row = await MemoryRepository(session).upsert_memory(
        ctx,
        scope=payload.scope,
        title=payload.title,
        text=payload.text,
        payload=payload.payload,
    )
    return _memory_out(row, score=1.0)


@router.post("/api/memory/search", response_model=list[MemoryOut])
async def search_memory(
    payload: MemorySearchIn,
    session: SessionDep,
    ctx: ContextDep,
) -> list[MemoryOut]:
    rows = await MemoryRepository(session).search(
        ctx,
        query=payload.query,
        scope=payload.scope,
        limit=payload.limit,
    )
    return [_memory_out(row, score=score) for row, score in rows]


@router.post("/api/self-update/plan", response_model=SelfUpdateOut)
async def plan_self_update(
    payload: SelfUpdatePlanIn,
    ctx: ContextDep,
) -> SelfUpdateOut:
    ensure_can_connect_account(ctx)
    try:
        candidate = await SelfUpdatePipeline(get_settings()).plan(
            source=payload.source,
            current_snapshot=payload.current_snapshot,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _self_update_out(candidate.as_payload())


@router.post("/api/self-update/run", response_model=SelfUpdateOut)
async def run_self_update_gate(
    payload: SelfUpdateRunIn,
    session: SessionDep,
    ctx: ContextDep,
) -> SelfUpdateOut:
    ensure_can_connect_account(ctx)
    try:
        candidate = await SelfUpdatePipeline(get_settings()).run_candidate_gate(
            source=payload.source,
            diff_text=payload.diff_text,
            expected_sha256=payload.expected_sha256,
            signature=payload.signature,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    row = await SelfUpdateRepository(session).save_run(
        ctx,
        source=candidate.source,
        status=candidate.status,
        current_snapshot=candidate.current_snapshot,
        candidate_snapshot=candidate.candidate_snapshot,
        gates=candidate.gates,
        payload=candidate.as_payload(),
    )
    data = candidate.as_payload()
    data["runId"] = row.id
    return _self_update_out(data)


@router.post("/api/claim-deadlines", response_model=ClaimDeadlineOut)
async def save_claim_deadline(
    payload: ClaimDeadlineIn,
    session: SessionDep,
    ctx: ContextDep,
) -> ClaimDeadlineOut:
    ensure_can_connect_account(ctx)
    row = await ClaimPolicyRepository(session).save_deadline_policy(
        ctx,
        platform=payload.platform,
        claim_type=payload.claim_type,
        days=payload.days,
        source_url=payload.source_url,
        note=payload.note,
    )
    return _claim_deadline_out(row)


@router.get("/api/claim-deadlines", response_model=list[ClaimDeadlineOut])
async def list_claim_deadlines(session: SessionDep, ctx: ContextDep) -> list[ClaimDeadlineOut]:
    rows = await ClaimPolicyRepository(session).list_deadline_policies(ctx)
    seen = {(row.platform, row.claim_type) for row in rows}
    defaults = [
        _default_claim_deadline_out(rule)
        for rule in default_claim_deadline_rules()
        if (rule.platform.value, rule.claim_type) not in seen
    ]
    return [_claim_deadline_out(row) for row in rows] + defaults


def _task_out(task) -> TaskOut:
    return TaskOut(
        taskId=task.task_id,
        moduleId=task.module_id.value,
        title=task.title,
        shortText=task.short_text,
        actionLabel=task.action_label,
        priority=task.priority,
        risk=task.risk.value,
        status=task.status.value,
        score=round(task.score, 4),
        moneyEffect=task.money_effect,
        confidence=task.confidence,
        deadlineAt=task.deadline_at.isoformat() if task.deadline_at else None,
        payload=task.payload,
    )


def _confirm_out(result) -> ConfirmOut:
    return ConfirmOut(
        taskId=result.task_id,
        status=result.status.value,
        text=_public_action_text(result.user_text),
        auditEvent=result.audit_event,
    )


def _public_action_text(text: str) -> str:
    normalized = text.strip()
    if normalized.startswith("Готово. "):
        return "Записал. " + normalized.removeprefix("Готово. ")
    if normalized.startswith("Готово "):
        return "Записал " + normalized.removeprefix("Готово ")
    return normalized


def _account_out(account) -> AccountOut:
    return AccountOut(
        accountId=account.account_id,
        platform=account.platform.value,
        title=account.title,
        status=account.status,
        tokenFingerprint=account.token_fingerprint,
        capabilities=account.capabilities,
        limitations=account.limitations,
    )


def _claim_deadline_out(row) -> ClaimDeadlineOut:
    needs_verification = OWNER_VERIFICATION_REQUIRED in (row.note or "")
    return ClaimDeadlineOut(
        policyId=row.id,
        platform=row.platform,
        claimType=row.claim_type,
        days=row.days,
        sourceUrl=row.source_url,
        note=row.note,
        sourceKind="owner",
        ownerVerified=not needs_verification,
        needsOwnerVerification=needs_verification,
    )


def _default_claim_deadline_out(rule) -> ClaimDeadlineOut:
    return ClaimDeadlineOut(
        policyId=f"baseline-{rule.platform.value}-{rule.claim_type}",
        platform=rule.platform.value,
        claimType=rule.claim_type,
        days=rule.days,
        sourceUrl=rule.source_url,
        note=rule.note,
        sourceKind="baseline",
        ownerVerified=False,
        needsOwnerVerification=True,
    )


def _plugin_out(row) -> PluginManifestOut:
    return PluginManifestOut(
        pluginId=row.plugin_id,
        label=row.label,
        surface=row.surface,
        moduleId=row.module_id,
        action=row.action,
        status=row.status,
        requiresConfirm=bool(row.requires_confirm),
        inputSchema=row.schema,
    )


def _memory_out(row, *, score: float) -> MemoryOut:
    return MemoryOut(
        memoryId=row.id,
        scope=row.scope,
        title=row.title,
        text=row.text,
        textHash=row.text_hash,
        embeddingModel=row.embedding_model,
        score=round(score, 6),
        payload=row.payload,
    )


def _self_update_out(payload: dict) -> SelfUpdateOut:
    return SelfUpdateOut(
        runId=payload.get("runId"),
        source=payload["source"],
        currentSnapshot=payload["currentSnapshot"],
        candidateSnapshot=payload["candidateSnapshot"],
        status=payload["status"],
        gates=payload["gates"],
        notes=list(payload.get("notes") or []),
    )
