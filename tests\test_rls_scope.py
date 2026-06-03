from operator_day.db import bind_tenant_scope
from operator_day.domain import Role, TenantContext


class FakeSession:
    def __init__(self) -> None:
        self.calls = []

    async def execute(self, statement, params=None):
        self.calls.append((str(statement), params))


async def test_bind_tenant_scope_sets_postgres_config() -> None:
    session = FakeSession()
    ctx = TenantContext(tenant_id="seller-rls", user_id="owner", role=Role.OWNER)

    await bind_tenant_scope(session, ctx, database_url="postgresql+asyncpg://db")

    assert "set_config" in session.calls[0][0]
    assert session.calls[0][1] == {"tenant_id": "seller-rls"}


async def test_bind_tenant_scope_skips_sqlite() -> None:
    session = FakeSession()
    ctx = TenantContext(tenant_id="seller-rls", user_id="owner", role=Role.OWNER)

    await bind_tenant_scope(session, ctx, database_url="sqlite+aiosqlite:///db.sqlite")

    assert session.calls == []
