import httpx

from operator_day.connectors.pagination import fetch_ozon_last_id_pages
from operator_day.connectors.transport import MarketplaceCredentials, MarketplaceTransport


async def test_fetch_ozon_last_id_pages_collects_until_empty_page() -> None:
    pages = [
        {"result": {"items": [{"id": 1}], "last_id": "a"}},
        {"result": {"items": [{"id": 2}], "last_id": "b"}},
        {"result": {"items": [], "last_id": ""}},
    ]
    seen_last_ids = []

    async def handler(request: httpx.Request) -> httpx.Response:
        body = request.read().decode("utf-8")
        seen_last_ids.append(body)
        return httpx.Response(200, json=pages.pop(0))

    transport = MarketplaceTransport(
        MarketplaceCredentials(platform="ozon", api_key="seller-secret", client_id="client-1"),
        http_transport=httpx.MockTransport(handler),
    )

    items = await fetch_ozon_last_id_pages(
        transport,
        "ProductAPI_GetProductList",
        {"filter": {"visibility": "ALL"}},
    )

    assert items == [{"id": 1}, {"id": 2}]
    assert '"last_id":"a"' in seen_last_ids[1].replace(" ", "")


async def test_fetch_ozon_last_id_pages_stops_on_repeated_cursor() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"result": {"items": [{"id": 1}], "last_id": "same"}})

    transport = MarketplaceTransport(
        MarketplaceCredentials(platform="ozon", api_key="seller-secret", client_id="client-1"),
        http_transport=httpx.MockTransport(handler),
    )

    items = await fetch_ozon_last_id_pages(
        transport,
        "ProductAPI_GetProductList",
        {},
        max_pages=5,
    )

    assert items == [{"id": 1}]
