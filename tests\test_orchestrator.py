from operator_day.brain.orchestrator import MorningOrchestrator
from operator_day.domain import ActionRisk, ModuleId, Role, TaskStatus, TenantContext
from operator_day.modules.implementations import ModuleRegistry


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
    assert result.audit_event["marketplace_operation"]["status"] == "planned"
    assert result.audit_event["marketplace_operation"]["planned_operation"]["dryRun"] is True
    assert result.audit_event["execution_lifecycle"]["stages"][2]["name"] == "marketplace_planned"
    assert result.audit_event["execution_lifecycle"]["rollback"]["mode"] == "discard_plan"


async def test_ads_confirmation_builds_marketplace_bid_plan() -> None:
    ctx = TenantContext(tenant_id="t1", user_id="u1", role=Role.OWNER)
    orchestrator = MorningOrchestrator()
    tasks = await orchestrator.collect_all(ctx)
    task = next(item for item in tasks if item.module_id == ModuleId.ADS)

    result = await orchestrator.execute_prepared(ctx, task)

    assert result.audit_event["action"] == "ads_bid_update_planned"
    assert result.audit_event["operation_id"] == "YM_UpdateCampaignBids"
    assert result.audit_event["marketplace_operation"]["planned_operation"]["safety"] == "write"
    assert result.audit_event["execution_lifecycle"]["workflow"] == "operator_day_confirmed_action"


async def test_reprice_confirmation_builds_marketplace_price_plan() -> None:
    ctx = TenantContext(tenant_id="t1", user_id="u1", role=Role.OWNER)
    orchestrator = MorningOrchestrator()
    tasks = await orchestrator.collect_all(ctx)
    task = next(item for item in tasks if item.module_id == ModuleId.REPRICER)

    result = await orchestrator.execute_prepared(ctx, task)

    assert result.audit_event["action"] == "price_update_planned"
    assert result.audit_event["target_price"] >= task.payload["hard_floor"]
    assert result.audit_event["marketplace_operation"]["planned_operation"]["dryRun"] is True


async def test_module_without_executor_is_not_marked_done() -> None:
    ctx = TenantContext(tenant_id="t1", user_id="u1", role=Role.OWNER)
    orchestrator = MorningOrchestrator()
    tasks = await orchestrator.collect_all(ctx)
    task = next(item for item in tasks if item.module_id == ModuleId.SUPPLIES)

    result = await orchestrator.execute_prepared(ctx, task)

    assert result.status == TaskStatus.FAILED
    assert result.audit_event["connector_status"] == "not_executable_yet"
    assert result.audit_event["execution_lifecycle"]["stages"][2]["name"] == "not_executable_yet"
