from operator_day.brain.orchestrator import MorningOrchestrator
from operator_day.domain import Role, TenantContext
from operator_day.modules.implementations import ModuleRegistry
from operator_day.skills_catalog import all_operator_capabilities


def test_operator_has_at_least_30_skills_and_plugins() -> None:
    capabilities = all_operator_capabilities()

    assert len(capabilities) >= 30
    assert any(item["kind"] == "skill" for item in capabilities)
    assert any(item["kind"] == "plugin" for item in capabilities)


async def test_every_action_has_10_mcp_checks_and_answer_basis() -> None:
    ctx = TenantContext(tenant_id="seller-skills", user_id="owner-skills", role=Role.OWNER)
    tasks = await MorningOrchestrator().collect_all(ctx)

    assert tasks
    for task in tasks:
        assert len(task.payload["mcp_checks"]) >= 10
        assert len(task.payload["skills"]) + len(task.payload["plugins"]) >= 30
        assert task.payload["answer_basis"]
        assert task.payload["skills"]
        assert task.payload["plugins"]


async def test_replay_covers_every_action_module_direction() -> None:
    ctx = TenantContext(tenant_id="seller-coverage", user_id="owner-coverage", role=Role.OWNER)
    tasks = await MorningOrchestrator().collect_all(ctx)
    emitted_modules = {task.module_id for task in tasks}
    registry_modules = {module.module_id for module in ModuleRegistry.default().modules}

    assert registry_modules == emitted_modules
