from httpx import ASGITransport, AsyncClient

from operator_day.domain import Role, TenantContext
from operator_day.main import create_app
from operator_day.repositories import ReadinessRepository


async def test_readiness_reports_modules_capabilities_and_blockers() -> None:
    headers = {"X-Tenant-Id": "ready-api", "X-User-Id": "owner", "X-Role": "owner"}
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        response = await client.get("/api/readiness", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["moduleCount"] == 23
    assert body["skillsAndPlugins"] >= 30
    assert body["checksPerAction"] == 10
    assert body["status"] == "ready_for_replay_pilot"
    assert body["mode"] == "replay"
    assert body["architectureGatePassed"] is False
    assert "real_marketplace_tokens" in body["blockers"]
    assert "claim_deadline_policies" in body["blockers"]
    assert "prod_llm_gate" in body["blockers"]


async def test_readiness_reports_live_blocked_until_account_is_validated() -> None:
    headers = {"X-Tenant-Id": "ready-live", "X-User-Id": "owner", "X-Role": "owner"}
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        await client.post(
            "/api/accounts",
            headers=headers,
            json={
                "platform": "ozon",
                "title": "Ozon",
                "apiKey": "ready-secret-token",
                "clientId": "123",
            },
        )
        response = await client.get("/api/readiness", headers=headers)

    body = response.json()
    assert body["status"] == "blocked_for_live_pilot"
    assert body["mode"] == "live"
    assert "marketplace_api_verification" in body["blockers"]
    assert "prod_llm_gate" in body["blockers"]


async def test_readiness_repository_records_architecture_gate_pass(session_factory) -> None:
    ctx = TenantContext(tenant_id="ready-gate", user_id="owner", role=Role.OWNER)
    async with session_factory() as session:
        repo = ReadinessRepository(session)
        before = await repo.has_passed_architecture_gate(ctx)
        await repo.record_architecture_gate_passed(
            ctx,
            model="claude-opus-4-8",
            tokens_estimate=123,
        )
        after = await repo.has_passed_architecture_gate(ctx)

    assert before is False
    assert after is True
