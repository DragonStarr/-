from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from operator_day.connectors.ozon_sync import OzonCatalogSync
from operator_day.connectors.transport import MarketplaceCredentials, MarketplaceTransport
from operator_day.db import bind_tenant_scope
from operator_day.domain import TenantContext
from operator_day.models import AuditLog
from operator_day.repositories import AccountRepository, CatalogRepository

CatalogLoader = Callable[[MarketplaceCredentials], Awaitable[dict[str, Any] | list[dict[str, Any]]]]
AccountValidator = Callable[[MarketplaceCredentials, str, dict], Awaitable[dict]]


def _catalog_probe_for_credentials(credentials: MarketplaceCredentials) -> tuple[str, dict, str]:
    if credentials.platform == "ozon":
        return "ProductAPI_GetProductList", {"filter": {}, "limit": 1}, "ozon"
    if credentials.platform == "wb":
        return (
            "WB_Content_GetCardsList",
            {"settings": {"cursor": {"limit": 1}, "filter": {"withPhoto": -1}}},
            "wb",
        )
    if credentials.platform == "ym":
        campaign_id = credentials.metadata.get("campaign_id")
        if not campaign_id:
            raise ValueError("Yandex Market catalog probe requires campaignId")
        return "YM_GetOfferPrices", {"campaign_id": campaign_id, "limit": 1}, "ym"
    raise ValueError("Catalog read probe is supported for Ozon, WB and Yandex Market")


async def plan_catalog_sync_for_account(
    session: AsyncSession,
    ctx: TenantContext,
    account_id: str,
) -> dict:
    await bind_tenant_scope(session, ctx)
    credentials = await AccountRepository(session).credentials_for_account(ctx, account_id)
    operation_id, payload, source = _catalog_probe_for_credentials(credentials)
    transport = MarketplaceTransport(credentials)
    planned_operation = await transport.call_operation(operation_id, payload, dry_run=True)
    session.add(
        AuditLog(
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            action="catalog_sync_planned",
            before_after={
                "account_id": account_id,
                "source": source,
                "operation_id": planned_operation["operationId"],
                "dry_run": True,
            },
        )
    )
    await session.commit()
    return {
        "account_id": account_id,
        "source": source,
        "dry_run": True,
        "planned_operation": planned_operation,
        "count": 0,
    }


async def validate_account_for_read_access(
    session: AsyncSession,
    ctx: TenantContext,
    account_id: str,
    *,
    dry_run: bool = False,
    validator: AccountValidator | None = None,
) -> dict:
    await bind_tenant_scope(session, ctx)
    credentials = await AccountRepository(session).credentials_for_account(ctx, account_id)
    operation_id, payload, source = _catalog_probe_for_credentials(credentials)
    transport = MarketplaceTransport(credentials)
    if dry_run:
        planned_operation = await transport.call_operation(operation_id, payload, dry_run=True)
        session.add(
            AuditLog(
                tenant_id=ctx.tenant_id,
                user_id=ctx.user_id,
                action="account_validation_planned",
                before_after={
                    "account_id": account_id,
                    "source": source,
                    "operation_id": operation_id,
                    "dry_run": True,
                },
            )
        )
        await session.commit()
        return {
            "account_id": account_id,
            "source": source,
            "status": "planned",
            "dry_run": True,
            "planned_operation": planned_operation,
        }
    if validator is None:
        await transport.call_operation(operation_id, payload)
    else:
        await validator(credentials, operation_id, payload)
    await AccountRepository(session).mark_account_validated(
        ctx,
        account_id=account_id,
        source=source,
        operation_id=operation_id,
    )
    return {
        "account_id": account_id,
        "source": source,
        "status": "validated",
        "dry_run": False,
        "planned_operation": None,
    }


async def sync_ozon_catalog_for_account(
    session: AsyncSession,
    ctx: TenantContext,
    account_id: str,
    *,
    loader: CatalogLoader | None = None,
) -> dict:
    return await sync_catalog_for_account(session, ctx, account_id, loader=loader)


async def sync_catalog_for_account(
    session: AsyncSession,
    ctx: TenantContext,
    account_id: str,
    *,
    loader: CatalogLoader | None = None,
) -> dict:
    await bind_tenant_scope(session, ctx)
    credentials = await AccountRepository(session).credentials_for_account(ctx, account_id)
    if loader is None:
        rows = await _load_catalog_rows(credentials)
    else:
        rows = _normalize_catalog_rows(credentials.platform, await loader(credentials))
    count = await CatalogRepository(session).upsert_products(
        ctx,
        account_id=account_id,
        source=credentials.platform,
        rows=rows,
    )
    session.add(
        AuditLog(
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            action=(
                "ozon_catalog_synced"
                if credentials.platform == "ozon"
                else "catalog_synced"
            ),
            before_after={
                "account_id": account_id,
                "count": count,
                "source": credentials.platform,
            },
        )
    )
    await session.commit()
    return {"account_id": account_id, "count": count, "source": credentials.platform}


async def _load_catalog_rows(credentials: MarketplaceCredentials) -> list[dict[str, Any]]:
    transport = MarketplaceTransport(credentials)
    if credentials.platform == "ozon":
        return _normalize_catalog_rows(
            credentials.platform,
            await OzonCatalogSync(transport).load_product_index(),
        )
    operation_id, payload, _source = _catalog_probe_for_credentials(credentials)
    response = await transport.call_operation(operation_id, payload)
    return _normalize_catalog_rows(credentials.platform, response)


def _normalize_catalog_rows(
    platform: str,
    payload: dict[str, Any] | list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if platform == "wb":
        return [
            _normalize_wb_card(card)
            for card in _first_list(payload, ("cards", "data.cards", "result.cards"))
        ]
    if platform == "ym":
        return [
            _normalize_yandex_offer(offer)
            for offer in _first_list(
                payload,
                (
                    "offers",
                    "items",
                    "result.offers",
                    "result.items",
                    "result.offerPrices",
                    "offerPrices",
                ),
            )
        ]
    return [
        _normalize_common_product(item)
        for item in _first_list(payload, ("items", "result.items", "result"))
    ]


def _normalize_common_product(item: dict[str, Any]) -> dict[str, Any]:
    sku = item.get("offer_id") or item.get("sku") or item.get("product_id") or item.get("id")
    title = item.get("title") or item.get("name") or sku
    return {
        "sku": str(sku or ""),
        "title": str(title or sku or ""),
        "price": _number(item.get("price")),
        "cost": _number(item.get("cost")),
        "stock": _number(
            item.get("stock")
            or item.get("quantity")
            or item.get("available")
            or item.get("stocks_count")
        ),
        "commission_rate": _number(
            item.get("commission_rate") or item.get("commissionRate") or item.get("commission")
        ),
        "rating": _number(item.get("rating") or item.get("ratingValue")),
        "payload": item,
    }


def _normalize_wb_card(card: dict[str, Any]) -> dict[str, Any]:
    sku = card.get("vendorCode") or card.get("nmID") or card.get("imtID") or card.get("sku")
    title = card.get("title") or card.get("object") or card.get("name") or sku
    price = _wb_price(card)
    return {
        "sku": str(sku or ""),
        "title": str(title or sku or ""),
        "price": price,
        "cost": _number(card.get("cost")),
        "stock": _number(
            card.get("stock")
            or card.get("quantity")
            or card.get("totalQuantity")
            or _nested_get(card, "stocks.total")
        ),
        "commission_rate": _number(
            card.get("commission_rate") or card.get("commissionRate") or card.get("commission")
        ),
        "rating": _number(card.get("rating") or card.get("nmRating") or card.get("ratingValue")),
        "payload": card,
    }


def _normalize_yandex_offer(offer: dict[str, Any]) -> dict[str, Any]:
    sku = offer.get("offerId") or offer.get("offer_id") or offer.get("shopSku") or offer.get("id")
    title = offer.get("name") or offer.get("title") or sku
    price = (
        _nested_get(offer, "price.value")
        or _nested_get(offer, "basicPrice.value")
        or _nested_get(offer, "price.current")
        or offer.get("price")
    )
    return {
        "sku": str(sku or ""),
        "title": str(title or sku or ""),
        "price": _number(price),
        "cost": _number(offer.get("cost")),
        "stock": _number(
            offer.get("stock")
            or offer.get("quantity")
            or _first_stock_count(offer.get("stocks"))
            or _nested_get(offer, "available.value")
            or _nested_get(offer, "stock.value")
        ),
        "commission_rate": _number(
            offer.get("commission_rate")
            or offer.get("commissionRate")
            or _nested_get(offer, "commission.value")
        ),
        "rating": _number(offer.get("rating") or offer.get("ratingValue")),
        "payload": offer,
    }


def _first_list(
    payload: dict[str, Any] | list[dict[str, Any]],
    paths: tuple[str, ...],
) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    for path in paths:
        value = _nested_get(payload, path)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _nested_get(payload: dict[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _first_stock_count(value: Any) -> Any:
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return (
            value[0].get("count")
            or value[0].get("quantity")
            or value[0].get("available")
            or value[0].get("stock")
        )
    return None


def _wb_price(card: dict[str, Any]) -> float:
    value, in_minor_units = _wb_price_value(card)
    amount = _number(value)
    return round(amount / 100, 2) if in_minor_units else amount


def _wb_price_value(card: dict[str, Any]) -> tuple[Any, bool]:
    for key in ("priceU", "discountedPriceU"):
        if card.get(key) is not None:
            return card.get(key), True
    for key in ("price", "discountedPrice"):
        if card.get(key) is not None:
            return card.get(key), False
    sizes = card.get("sizes")
    if isinstance(sizes, list) and sizes:
        first_size = sizes[0]
        if isinstance(first_size, dict):
            for key in ("priceU", "discountedPriceU"):
                if first_size.get(key) is not None:
                    return first_size.get(key), True
            for key in ("price", "discountedPrice"):
                if first_size.get(key) is not None:
                    return first_size.get(key), False
    return None, False


def _number(value: Any) -> float:
    if isinstance(value, dict):
        value = value.get("value") or value.get("current") or value.get("price")
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
