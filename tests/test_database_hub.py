from sqlalchemy.ext.asyncio import AsyncSession

from operator_day.connectors.replay import DatabaseReplayHub
from operator_day.domain import Platform, Role, TenantContext
from operator_day.models import Product


async def test_database_replay_hub_prefers_tenant_products(session_factory) -> None:
    ctx = TenantContext(tenant_id="db-hub-tenant", user_id="owner", role=Role.OWNER)
    other_ctx = TenantContext(tenant_id="other-tenant", user_id="owner", role=Role.OWNER)
    async with session_factory() as session:
        assert isinstance(session, AsyncSession)
        session.add(
            Product(
                tenant_id=ctx.tenant_id,
                account_id="account-1",
                sku="REAL-1",
                title="Реальный товар",
                category="ozon",
                price=990,
                cost=500,
            )
        )
        session.add(
            Product(
                tenant_id=other_ctx.tenant_id,
                account_id="account-2",
                sku="OTHER-1",
                title="Чужой товар",
                category="ozon",
                price=1,
                cost=1,
            )
        )
        await session.commit()

        products = await DatabaseReplayHub(session, ctx).products()

    assert [product.sku for product in products] == ["REAL-1"]
    assert products[0].platform == Platform.OZON
    assert products[0].name == "Реальный товар"


async def test_empty_database_hub_does_not_substitute_demo_fixtures(session_factory) -> None:
    ctx = TenantContext(tenant_id="empty-db-hub-tenant", user_id="owner", role=Role.OWNER)
    async with session_factory() as session:
        hub = DatabaseReplayHub(session, ctx)

        assert await hub.products() == []
        assert await hub.reviews() == []
        assert await hub.claim_candidates() == []
        assert await hub.pvz_points() == []
        assert await hub.operational_records("alerts") == []
        assert await hub.operational_records("cash_ops") == []
