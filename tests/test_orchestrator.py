import pytest

from operator_day.brain.orchestrator import MorningOrchestrator
from operator_day.connectors.replay import ReplayHub
from operator_day.domain import (
    ActionRisk,
    ModuleId,
    Platform,
    ReviewSnapshot,
    Role,
    TaskAction,
    TaskStatus,
    TenantContext,
)
from operator_day.modules.base import OperatorModule
from operator_day.modules.implementations import (
    AccountGuardModule,
    AdsModule,
    ModuleRegistry,
    ReviewsModule,
)


class FakeReplay:
    def __init__(self) -> None:
        self.called = False

    async def execute_marketplace_operation(self, *args, **kwargs):
        self.called = True
        return {"status": "planned", "planned_operation": {"dryRun": True}}


class FailingReviewReplay:
    def __init__(self) -> None:
        self.sent = False
        self.operation_called = False

    async def reviews(self) -> list[ReviewSnapshot]:
        return [
            ReviewSnapshot(
                platform=Platform.OZON,
                review_id="review-fails-after-draft",
                sku="OZ-501",
                rating=5,
                text="Покупатель доволен товаром.",
            )
        ]

    async def execute_marketplace_operation(self, *args, **kwargs) -> dict:
        self.operation_called = True
        raise RuntimeError("marketplace unavailable")

    async def send_review_answer(self, review_id: str, answer: str) -> dict[str, str]:
        self.sent = True
        return {"mode": "database", "review_id": review_id, "status": "prepared", "answer": answer}


def test_registry_contains_23_module_contracts() -> None:
    module_ids = {module.module_id for module in ModuleRegistry.default().modules}

    assert len(module_ids) == 22
    assert len(module_ids) + 1 == 23
    assert ModuleId.MORNING not in module_ids
    assert ModuleId.ADS in module_ids
    assert ModuleId.CLAIMS in module_ids
    assert ModuleId.NICHES in module_ids
    assert ModuleId.CONTENT in module_ids
    assert ModuleId.ACCOUNT_GUARD in module_ids


def test_every_operator_module_has_explicit_execution_contract() -> None:
    modules = ModuleRegistry.default().modules

    inherited_fallbacks = [
        module.module_id.value
        for module in modules
        if module.__class__.execute is OperatorModule.execute
    ]

    assert inherited_fallbacks == []


async def test_every_collected_action_has_specific_artifact_type() -> None:
    ctx = TenantContext(tenant_id="t1", user_id="u1", role=Role.OWNER)
    tasks = await MorningOrchestrator().collect_all(ctx)

    generic_artifacts = [
        (task.module_id.value, task.title)
        for task in tasks
        if task.payload.get("artifact_type") == "operator_plan"
    ]

    assert generic_artifacts == []


async def test_morning_top_returns_five_ranked_actions() -> None:
    ctx = TenantContext(tenant_id="t1", user_id="u1", role=Role.OWNER)
    tasks = await MorningOrchestrator().morning_top(ctx)

    assert len(tasks) == 5
    assert tasks[0].score >= tasks[-1].score
    assert tasks[0].has_near_deadline()
    assert any(task.risk == ActionRisk.HUMAN for task in tasks)


async def test_confirm_marks_action_done_or_escalated() -> None:
    ctx = TenantContext(tenant_id="t1", user_id="u1", role=Role.OWNER)
    orchestrator = MorningOrchestrator()
    tasks = await orchestrator.morning_top(ctx)

    result = await orchestrator.confirm(ctx, tasks[0].task_id)

    assert result.task_id == tasks[0].task_id
    assert result.audit_event["tenant_id"] == "t1"


async def test_positive_review_confirmation_uses_llm_fallback() -> None:
    ctx = TenantContext(tenant_id="t1", user_id="u1", role=Role.OWNER)
    orchestrator = MorningOrchestrator()
    tasks = await orchestrator.collect_all(ctx)
    task = next(
        item
        for item in tasks
        if item.module_id == ModuleId.REVIEWS and item.risk == ActionRisk.CONFIRM
    )

    result = await orchestrator.execute_prepared(ctx, task)

    assert result.audit_event["action"] == "review_answer_sent"
    assert result.audit_event["llm_model"] == "offline-template"
    assert result.audit_event["connector_status"] == "accepted"
    assert result.status == TaskStatus.PLANNED
    assert not result.user_text.startswith("Готово")
    assert "внешний кабинет не менял" in result.user_text.lower()
    assert result.audit_event["marketplace_operation"]["status"] == "planned"
    assert result.audit_event["marketplace_operation"]["planned_operation"]["dryRun"] is True
    assert result.audit_event["execution_lifecycle"]["stages"][2]["name"] == "marketplace_planned"
    assert result.audit_event["execution_lifecycle"]["rollback"]["mode"] == "discard_plan"


async def test_negative_review_escalation_records_local_artifact_contract() -> None:
    ctx = TenantContext(tenant_id="t1", user_id="u1", role=Role.OWNER)
    orchestrator = MorningOrchestrator()
    tasks = await orchestrator.collect_all(ctx)
    task = next(
        item
        for item in tasks
        if item.module_id == ModuleId.REVIEWS and item.risk == ActionRisk.HUMAN
    )

    result = await orchestrator.execute_prepared(ctx, task)

    assert result.status == TaskStatus.ESCALATED
    assert result.audit_event["action"] == "review_escalation_recorded"
    assert result.audit_event["marketplace_write"] == "not_attempted"
    assert result.audit_event["artifact"]["artifact_type"] == "review_reply_draft"
    assert result.audit_event["execution_lifecycle"]["stages"][2]["name"] == "human_escalated"


async def test_every_confirmed_action_has_explicit_execution_audit_contract() -> None:
    ctx = TenantContext(tenant_id="t1", user_id="u1", role=Role.OWNER)
    orchestrator = MorningOrchestrator()
    tasks = await orchestrator.collect_all(ctx)

    assert tasks
    for task in tasks:
        result = await orchestrator.execute_prepared(ctx, task)
        audit = result.audit_event
        has_marketplace_operation = "marketplace_operation" in audit
        has_local_artifact = (
            audit.get("marketplace_write") == "not_attempted" and "artifact" in audit
        )
        has_blocked_write = (
            result.status == TaskStatus.FAILED and audit.get("marketplace_write") == "blocked"
        )

        assert "execution_lifecycle" in audit
        assert has_marketplace_operation or has_local_artifact or has_blocked_write, (
            task.module_id.value,
            task.title,
            audit,
        )


async def test_review_answer_is_not_marked_prepared_before_marketplace_plan() -> None:
    ctx = TenantContext(tenant_id="t1", user_id="u1", role=Role.OWNER)
    module = ReviewsModule()
    replay = FailingReviewReplay()
    tasks = await module.collect_actions(ctx, replay)  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="marketplace unavailable"):
        await module.execute(ctx, tasks[0], replay)  # type: ignore[arg-type]

    assert replay.operation_called is True
    assert replay.sent is False


async def test_ads_confirmation_builds_marketplace_bid_plan() -> None:
    ctx = TenantContext(tenant_id="t1", user_id="u1", role=Role.OWNER)
    task = TaskAction(
        module_id=ModuleId.ADS,
        title="Ставка",
        short_text="Проверка",
        action_label="Проверить",
        payload={
            "platform": "ym",
            "sku": "SKU-1",
            "bid_after": 50,
            "bid_before": 80,
            "expected_drr": 0.18,
            "business_id": "business-123",
        },
        priority=5,
        risk=ActionRisk.CONFIRM,
    )

    result = await AdsModule().execute(ctx, task, ReplayHub())

    assert result.status == TaskStatus.PLANNED
    assert result.audit_event["action"] == "ads_bid_update_planned"
    assert not result.user_text.startswith("Готово")
    assert "внешний кабинет не менял" in result.user_text.lower()
    assert result.audit_event["operation_id"] == "YM_UpdateCampaignBids"
    assert result.audit_event["marketplace_operation"]["planned_operation"]["safety"] == "write"


async def test_ads_confirmation_without_business_id_does_not_call_connector() -> None:
    ctx = TenantContext(tenant_id="t1", user_id="u1", role=Role.OWNER)
    task = TaskAction(
        module_id=ModuleId.ADS,
        title="Ставка",
        short_text="Проверка",
        action_label="Проверить",
        payload={"platform": "ym", "sku": "SKU-1", "bid_after": 50},
        priority=5,
        risk=ActionRisk.CONFIRM,
    )
    replay = FakeReplay()

    result = await AdsModule().execute(ctx, task, replay)  # type: ignore[arg-type]

    assert result.status == TaskStatus.FAILED
    assert result.audit_event["reason"] == "missing_business_id"
    assert replay.called is False


async def test_campaign_stop_without_campaign_id_does_not_call_connector() -> None:
    ctx = TenantContext(tenant_id="t1", user_id="u1", role=Role.OWNER)
    task = TaskAction(
        module_id=ModuleId.ACCOUNT_GUARD,
        title="Риск",
        short_text="Проверка",
        action_label="Остановить",
        payload={"platform": "ozon", "risk_type": "click_fraud"},
        priority=5,
        risk=ActionRisk.CONFIRM,
    )
    replay = FakeReplay()

    result = await AccountGuardModule().execute(ctx, task, replay)  # type: ignore[arg-type]

    assert result.status == TaskStatus.FAILED
    assert result.audit_event["reason"] == "missing_campaign_id"
    assert replay.called is False


async def test_reprice_confirmation_builds_marketplace_price_plan() -> None:
    ctx = TenantContext(tenant_id="t1", user_id="u1", role=Role.OWNER)
    orchestrator = MorningOrchestrator()
    tasks = await orchestrator.collect_all(ctx)
    task = next(item for item in tasks if item.module_id == ModuleId.REPRICER)

    result = await orchestrator.execute_prepared(ctx, task)

    assert result.status == TaskStatus.PLANNED
    assert result.audit_event["action"] == "price_update_planned"
    assert not result.user_text.startswith("Готово")
    assert "внешний кабинет не менял" in result.user_text.lower()
    assert task.payload["platform"] in {"ozon", "wb"}
    assert result.audit_event["operation_id"] in {
        "ProductAPI_ImportPrices",
        "WB_Prices_UploadTask",
    }
    assert result.audit_event["target_price"] >= task.payload["hard_floor"]
    assert result.audit_event["marketplace_operation"]["planned_operation"]["dryRun"] is True


async def test_local_module_records_artifact_without_marketplace_write() -> None:
    ctx = TenantContext(tenant_id="t1", user_id="u1", role=Role.OWNER)
    orchestrator = MorningOrchestrator()
    tasks = await orchestrator.collect_all(ctx)
    task = next(item for item in tasks if item.module_id == ModuleId.SUPPLIES)

    result = await orchestrator.execute_prepared(ctx, task)

    assert result.status == TaskStatus.DONE
    assert not result.user_text.startswith("Готово")
    assert result.audit_event["connector_status"] in {"planned", "recorded"}
    assert result.audit_event["marketplace_write"] == "not_attempted"
    assert result.audit_event["artifact"]["artifact_type"] == "supply_plan"
    assert result.audit_event["execution_lifecycle"]["stages"][2]["name"] == "local_action_recorded"
