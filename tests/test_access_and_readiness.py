import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from operator_day.main import create_app
from operator_day.models import Account, ActionExecution, AuditLog


def _headers(
    *,
    tenant: str = "seller-a",
    user: str = "owner-a",
    role: str = "owner",
    idem: str | None = None,
) -> dict[str, str]:
    values = {"X-Tenant-Id": tenant, "X-User-Id": user, "X-Role": role}
    if idem:
        values["X-Idempotency-Key"] = idem
    return values


async def test_api_uses_tenant_context_from_headers() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        response = await client.get("/api/tasks/morning", headers=_headers(tenant="seller-a"))
        other_response = await client.get("/api/tasks", headers=_headers(tenant="seller-b"))

    assert response.status_code == 200
    assert other_response.status_code == 200
    assert other_response.json() == []


async def test_api_rejects_invalid_context_headers() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/tasks/morning",
            headers=_headers(tenant="../bad", role="owner"),
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Неверный контекст продавца"


async def test_confirm_is_idempotent_by_key() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        tasks_response = await client.get("/api/tasks/morning", headers=_headers())
        task = tasks_response.json()[0]
        first = await client.post(
            f"/api/tasks/{task['taskId']}/confirm",
            headers=_headers(idem="same-click"),
        )
        second = await client.post(
            f"/api/tasks/{task['taskId']}/confirm",
            headers=_headers(idem="same-click"),
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()


async def test_non_owner_cannot_confirm_marketplace_write() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        tasks_response = await client.get("/api/tasks/morning", headers=_headers())
        task = tasks_response.json()[0]
        response = await client.post(
            f"/api/tasks/{task['taskId']}/confirm",
            headers=_headers(role="pvz_operator", idem="pvz-denied"),
        )

    assert response.status_code == 403


async def test_account_connect_encrypts_token_and_returns_capabilities() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/accounts",
            headers=_headers(),
            json={
                "platform": "ozon",
                "title": "Ozon основной",
                "apiKey": "ozon-secret-token",
                "clientId": "123456",
                "performanceClientId": "perf-id",
                "performanceClientSecret": "perf-secret",
            },
        )
        capabilities = await client.get("/api/accounts/capabilities", headers=_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["platform"] == "ozon"
    assert body["tokenFingerprint"]
    assert "secret" not in str(body).lower()
    assert capabilities.status_code == 200
    assert capabilities.json()[0]["capabilities"]["ads"] == "ready"


@pytest.mark.parametrize("path", ["/api/tasks/morning", "/api/tasks"])
async def test_security_headers_present_on_api(path: str) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        response = await client.get(path, headers=_headers())

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


async def test_repositories_store_single_execution_for_same_idempotency_key(session_factory):
    from operator_day.brain.orchestrator import MorningOrchestrator
    from operator_day.domain import Role, TenantContext
    from operator_day.repositories import TaskRepository

    ctx = TenantContext(tenant_id="seller-store", user_id="owner-store", role=Role.OWNER)
    orchestrator = MorningOrchestrator()
    async with session_factory() as session:
        repo = TaskRepository(session)
        tasks = await orchestrator.morning_top(ctx, limit=1)
        await repo.save_tasks(ctx, tasks)
        result = await orchestrator.execute_prepared(ctx, tasks[0])

        await repo.save_result(ctx, tasks[0], result, idempotency_key="idem-1")
        await repo.save_result(ctx, tasks[0], result, idempotency_key="idem-1")

        executions = (await session.execute(select(ActionExecution))).scalars().all()
        audit_rows = (await session.execute(select(AuditLog))).scalars().all()

    assert len(executions) == 1
    assert len(audit_rows) == 1


async def test_account_repository_does_not_store_plain_secret(session_factory) -> None:
    from operator_day.domain import Role, TenantContext
    from operator_day.repositories import AccountRepository

    ctx = TenantContext(tenant_id="seller-account", user_id="owner-account", role=Role.OWNER)
    async with session_factory() as session:
        row = await AccountRepository(session).connect_account(
            ctx,
            platform="wb",
            title="WB",
            secret="plain-secret-value",
            metadata={"supplier": "main"},
        )
        stored = await session.get(Account, row.account_id)

    assert stored is not None
    assert "plain-secret-value" not in stored.token_enc
    assert row.token_fingerprint
