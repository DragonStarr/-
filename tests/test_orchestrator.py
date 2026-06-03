from operator_day.brain.orchestrator import MorningOrchestrator
from operator_day.domain import ActionRisk, ModuleId, Role, TenantContext
from operator_day.modules.implementations import ModuleRegistry


def test_registry_contains_23_module_contracts() -> None:
    module_ids = {module.module_id for module in ModuleRegistry.default().modules}

    assert len(module_ids) == 22
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
