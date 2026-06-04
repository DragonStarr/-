from sqlalchemy import select

from operator_day.connectors.live_sync import (
    plan_catalog_sync_for_account,
    sync_catalog_for_account,
    sync_ozon_catalog_for_account,
    validate_account_for_read_access,
)
from operator_day.connectors.replay import DatabaseReplayHub
from operator_day.domain import Role, TenantContext
from operator_day.models import Account, AuditLog, Product, Sale, Stock
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


async def test_ozon_performance_credentials_are_encrypted_separately(session_factory) -> None:
    ctx = TenantContext(tenant_id="sync-perf", user_id="owner", role=Role.OWNER)
    async with session_factory() as session:
        account = await AccountRepository(session).connect_account(
            ctx,
            platform="ozon",
            title="Ozon",
            secret="seller-secret",
            metadata={
                "client_id": "client-1",
                "performance_client_id": "perf-client",
                "performance_client_secret": "perf-secret",
                "review_management_subscription": True,
            },
        )
        stored = await session.get(Account, account.account_id)
        credentials = await AccountRepository(session).performance_credentials_for_account(
            ctx,
            account.account_id,
        )

    assert stored is not None
    assert "perf-secret" not in str(stored.payload)
    assert stored.payload["performance_client_secret"] is True
    assert stored.payload["performance_client_secret_enc"]
    assert credentials.platform == "ozon_performance"
    assert credentials.client_id == "perf-client"
    assert credentials.api_key == "perf-secret"


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
                    "totalQuantity": 8,
                    "nmRating": 4.7,
                    "commissionRate": 0.21,
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
        stock = (await session.execute(select(Stock))).scalar_one()
        audit = (await session.execute(select(AuditLog))).scalars().all()

    assert result["source"] == "wb"
    assert result["count"] == 1
    assert product.sku == "WB-123"
    assert product.title == "WB product"
    assert product.price == 1499
    assert product.rating == 4.7
    assert product.commission_rate == 0.21
    assert stock.quantity == 8
    assert audit[-1].action == "catalog_synced"
    assert "wb-secret-token" not in str(audit[-1].before_after)


async def test_sync_wb_catalog_converts_minor_price_units(session_factory) -> None:
    ctx = TenantContext(tenant_id="sync-wb-price-u", user_id="owner", role=Role.OWNER)

    async def fake_loader(credentials):
        return {
            "cards": [
                {
                    "vendorCode": "WB-KOPECKS",
                    "title": "WB kopeck product",
                    "sizes": [{"priceU": 149900}],
                    "totalQuantity": 3,
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
        await sync_catalog_for_account(session, ctx, account.account_id, loader=fake_loader)
        product = (await session.execute(select(Product))).scalar_one()

    assert product.price == 1499


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
                        "stocks": [{"type": "FIT", "count": 11}],
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
        stock = (await session.execute(select(Stock))).scalar_one()

    assert result["source"] == "ym"
    assert result["count"] == 1
    assert product.sku == "YM-1"
    assert product.title == "Yandex product"
    assert product.price == 777
    assert stock.quantity == 11


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


async def test_validated_read_account_still_needs_write_scope_verification(
    session_factory,
) -> None:
    ctx = TenantContext(tenant_id="sync-seller-write-scope", user_id="owner", role=Role.OWNER)
    async with session_factory() as session:
        account = await AccountRepository(session).connect_account(
            ctx,
            platform="ozon",
            title="Ozon",
            secret="seller-secret",
                metadata={
                    "client_id": "client-1",
                    "performance_client_id": "perf-id",
                    "performance_client_secret": True,
                    "review_management_subscription": True,
                },
            )
        await AccountRepository(session).mark_account_validated(
            ctx,
            account_id=account.account_id,
            source="ozon",
            operation_id="ProductAPI_GetProductList",
        )

        missing = await AccountRepository(session).missing_write_scope_verifications(ctx)
        verified = await AccountRepository(session).mark_write_scopes_verified(
            ctx,
            account_id=account.account_id,
            scopes=["catalog", "reviews", "unknown"],
            source_url="https://seller.example.test/scopes",
            evidence="safe write capability probe passed in seller cabinet",
        )
        missing_after = await AccountRepository(session).missing_write_scope_verifications(ctx)

    assert "ozon:catalog" in missing
    assert "ozon:reviews" in missing
    assert "ozon:ads" in missing
    assert verified == ["catalog", "reviews"]
    assert missing_after == ["ozon:ads"]


async def test_database_replay_products_use_stock_rating_commission_and_sales(
    session_factory,
) -> None:
    from operator_day.repositories import SalesRepository

    ctx = TenantContext(tenant_id="replay-real-data", user_id="owner", role=Role.OWNER)
    async with session_factory() as session:
        account = await AccountRepository(session).connect_account(
            ctx,
            platform="ozon",
            title="Ozon",
            secret="seller-secret",
            metadata={"client_id": "client-1"},
        )
        await sync_catalog_for_account(
            session,
            ctx,
            account.account_id,
            loader=lambda _credentials: _catalog_loader_with_real_metrics(),
        )
        await SalesRepository(session).import_sales(
            ctx,
            account_id=account.account_id,
            rows=[
                {
                    "platform": "ozon",
                    "sale_id": "sale-1",
                    "sku": "SKU-METRIC",
                    "soldAt": "2026-06-01T10:00:00+00:00",
                    "quantity": 12,
                    "revenue": 12000,
                }
            ],
        )
        snapshot = (await DatabaseReplayHub(session, ctx).products())[0]
        sale_rows = (await session.execute(select(Sale))).scalars().all()

    assert snapshot.sku == "SKU-METRIC"
    assert snapshot.stock == 17
    assert snapshot.rating == 4.9
    assert snapshot.commission_rate == 0.19
    assert snapshot.daily_sales is not None
    assert snapshot.daily_sales > 0
    assert snapshot.data_sources["stock"] == "stocks"
    assert snapshot.data_sources["daily_sales"] == "sales"
    assert len(sale_rows) == 1


async def test_database_replay_products_keep_missing_stock_unknown(
    session_factory,
) -> None:
    ctx = TenantContext(tenant_id="replay-missing-stock", user_id="owner", role=Role.OWNER)
    async with session_factory() as session:
        account = await AccountRepository(session).connect_account(
            ctx,
            platform="ozon",
            title="Ozon",
            secret="seller-secret",
            metadata={"client_id": "client-1"},
        )
        session.add(
            Product(
                tenant_id=ctx.tenant_id,
                account_id=account.account_id,
                sku="NO-STOCK",
                title="No stock product",
                category="ozon",
                price=1000,
                cost=700,
                commission_rate=0.12,
                rating=4.5,
                payload={},
            )
        )
        await session.commit()
        snapshot = (await DatabaseReplayHub(session, ctx).products())[0]

    assert snapshot.stock is None
    assert snapshot.data_sources["stock"] == "missing"


async def _catalog_loader_with_real_metrics():
    return {
        "items": [
            {
                "offer_id": "SKU-METRIC",
                "title": "Metric product",
                "price": 1000,
                "cost": 500,
                "stock": 17,
                "rating": 4.9,
                "commissionRate": 0.19,
            }
        ]
    }
