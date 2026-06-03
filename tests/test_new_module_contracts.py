from operator_day.brain.orchestrator import MorningOrchestrator
from operator_day.domain import ActionRisk, ModuleId, Role, TenantContext


async def test_new_modules_payload_contracts_are_complete() -> None:
    ctx = TenantContext(tenant_id="seller-new-modules", user_id="owner", role=Role.OWNER)
    tasks = await MorningOrchestrator().collect_all(ctx)
    by_module = {task.module_id: task for task in tasks}

    ads = by_module[ModuleId.ADS]
    assert ads.risk == ActionRisk.CONFIRM
    assert ads.payload["needs_api_verification"] is True
    assert ads.payload["target_drr"] > 0
    assert ads.payload["bid_after"] < ads.payload["bid_before"]

    claims = by_module[ModuleId.CLAIMS]
    assert claims.risk == ActionRisk.HUMAN
    assert claims.deadline_at is not None
    assert claims.payload["claim_deadline_needs_verification"] is True
    assert claims.payload["evidence"]

    niches = by_module[ModuleId.NICHES]
    assert niches.payload["demand_trend"]
    assert niches.payload["suppliers"]
    assert niches.confidence <= 0.5

    content = by_module[ModuleId.CONTENT]
    assert content.payload["service_mode"] == "external_subscription"
    assert content.payload["image_generation_in_house"] is False

    guard = by_module[ModuleId.ACCOUNT_GUARD]
    assert guard.payload["whitehat_only"] is True
    assert guard.deadline_at is not None
