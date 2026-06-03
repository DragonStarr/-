from sqlalchemy import select

from operator_day.connectors.live_sync import (
    plan_catalog_sync_for_account,
    sync_catalog_for_account,
    sync_ozon_catalog_for_account,
    validate_account_for_read_access,
)
from operator_day.domain import Role, TenantContext
from operator_day.models import Account, AuditLog, Product
from operator_day.repositories import AccountRepository


async def test_account_credentials_decrypt_only_inside_repository(session_factory) -> None:
    ctx = TenantContext(tenant_id="sync-seller", user_id="owner", role=Role.OWNER)
    async with session_factory() as session:
        account = await AccountRepository(session).connect_account(
            ctx,
            platform="ozon",
            title="Ozon",
            secret="seller-secret",
            metadata={"client_id": "client-1"},
        )
        credentials = await AccountRepository(session).credentials_for_account(
            ctx,
            account.account_id,
        )

    assert credentials.api_key == "seller-secret"
    assert credentials.client_id == "client-1"


async def test_sync_ozon_catalog_for_account_writes_audit(session_factory) -> None:
    ctx = TenantContext(tenant_id="sync-seller-2", user_id="owner", role=Role.OWNER)

    async def fake_loader(credentials):
        assert credentials.api_key == "seller-secret"
        return [{"product_id": "1", "offer_id": "SKU-1"}]

    async with session_factory() as session:
        account = await AccountRepository(session).connect_account(
            ctx,
            platform="ozon",
            title="Ozon",
            secret="seller-secret",
            metadata={"client_id": "client-1"},
        )
        result = await sync_ozon_catalog_for_account(
            session,
            ctx,
            account.account_id,
            loader=fake_loader,
        )
        audit = (await session.execute(select(AuditLog))).scalars().all()
        products = (await session.execute(select(Product))).scalars().all()

    assert result["count"] == 1
    assert audit[-1].action == "ozon_catalog_synced"
    assert "seller-secret" not in str(audit[-1].before_after)
    assert products[0].tenant_id == ctx.tenant_id
    assert products[0].account_id == account.account_id
    assert products[0].sku == "SKU-1"


async def test_sync_wb_catalog_for_account_normalizes_cards(session_factory) -> None:
    ctx = TenantContext(tenant_id="sync-wb", user_id="owner", role=Role.OWNER)

    async def fake_loader(credentials):
        assert credentials.api_key == "wb-secret-token"
        return {
            "cards": [
                {
                    "nmID": 123,
                    "vendorCode": "WB-123",
                    "title": "WB product",
                    "sizes": [{"price": 1499}],
                }
            ]
        }

    async with session_factory() as session:
        account = await AccountRepository(session).connect_account(
            ctx,
            platform="wb",
            title="WB",
            secret="wb-secret-token",
            metadata={},
        )
        result = await sync_catalog_for_account(
            session,
            ctx,
            account.account_id,
            loader=fake_loader,
        )
        product = (await session.execute(select(Product))).scalar_one()
        audit = (await session.execute(select(AuditLog))).scalars().all()

    assert result["source"] == "wb"
    assert result["count"] == 1
    assert product.sku == "WB-123"
    assert product.title == "WB product"
    assert product.price == 1499
    assert audit[-1].action == "catalog_synced"
    assert "wb-secret-token" not in str(audit[-1].before_after)


async def test_sync_yandex_catalog_for_account_normalizes_offers(session_factory) -> None:
    ctx = TenantContext(tenant_id="sync-ym", user_id="owner", role=Role.OWNER)

    async def fake_loader(credentials):
        assert credentials.api_key == "ym-secret-token"
        return {
            "result": {
                "offers": [
                    {
                        "offerId": "YM-1",
                        "name": "Yandex product",
                        "price": {"value": 777},
                    }
                ]
            }
        }

    async with session_factory() as session:
        account = await AccountRepository(session).connect_account(
            ctx,
            platform="ym",
            title="Yandex",
            secret="ym-secret-token",
            metadata={"campaign_id": "321"},
        )
        result = await sync_catalog_for_account(
            session,
            ctx,
            account.account_id,
            loader=fake_loader,
        )
        product = (await session.execute(select(Product))).scalar_one()

    assert result["source"] == "ym"
    assert result["count"] == 1
    assert product.sku == "YM-1"
    assert product.title == "Yandex product"
    assert product.price == 777


async def test_plan_catalog_sync_returns_safe_dry_run_without_secret(session_factory) -> None:
    ctx = TenantContext(tenant_id="sync-seller-3", user_id="owner", role=Role.OWNER)
    async with session_factory() as session:
        account = await AccountRepository(session).connect_account(
            ctx,
            platform="wb",
            title="WB",
            secret="wb-secret-token",
            metadata={},
        )
        result = await plan_catalog_sync_for_account(session, ctx, account.account_id)

    assert result["dry_run"] is True
    assert result["planned_operation"]["operationId"] == "WB_Content_GetCardsList"
    assert "wb-secret-token" not in str(result)


async def test_plan_catalog_sync_supports_yandex_market_campaign_id(session_factory) -> None:
    ctx = TenantContext(tenant_id="sync-seller-ym", user_id="owner", role=Role.OWNER)
    async with session_factory() as session:
        account = await AccountRepository(session).connect_account(
            ctx,
            platform="ym",
            title="Yandex",
            secret="ym-secret-token",
            metadata={"campaign_id": "321"},
        )
        result = await plan_catalog_sync_for_account(session, ctx, account.account_id)

    assert result["source"] == "ym"
    assert result["planned_operation"]["operationId"] == "YM_GetOfferPrices"
    assert result["planned_operation"]["url"].endswith("/v2/campaigns/321/offer-prices")
    assert "ym-secret-token" not in str(result)


async def test_validate_account_live_marks_account_validated_and_redacts_secret(
    session_factory,
) -> None:
    ctx = TenantContext(tenant_id="sync-seller-4", user_id="owner", role=Role.OWNER)

    async def fake_validator(credentials, operation_id, payload):
        assert credentials.api_key == "seller-secret"
        assert operation_id == "ProductAPI_GetProductList"
        assert payload["limit"] == 1
        return {"result": {"items": []}}

    async with session_factory() as session:
        account = await AccountRepository(session).connect_account(
            ctx,
            platform="ozon",
            title="Ozon",
            secret="seller-secret",
            metadata={"client_id": "client-1"},
        )
        result = await validate_account_for_read_access(
            session,
            ctx,
            account.account_id,
            validator=fake_validator,
        )
        row = await session.get(Account, account.account_id)
        audit = (await session.execute(select(AuditLog))).scalars().all()

    assert result["status"] == "validated"
    assert row is not None
    assert row.status == "validated"
    assert audit[-1].action == "account_validated"
    assert "seller-secret" not in str(audit[-1].before_after)
