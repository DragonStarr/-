import httpx
import pytest

from operator_day.connectors.transport import (
    MarketplaceApiError,
    MarketplaceCredentials,
    MarketplaceTransport,
)


async def test_transport_calls_read_operation_with_ozon_headers() -> None:
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["client_id"] = request.headers.get("Client-Id")
        seen["api_key"] = request.headers.get("Api-Key")
        return httpx.Response(200, json={"result": {"items": []}})

    transport = MarketplaceTransport(
        MarketplaceCredentials(platform="ozon", api_key="seller-secret", client_id="client-1"),
        http_transport=httpx.MockTransport(handler),
    )

    response = await transport.call_operation("ProductAPI_GetProductList", {"filter": {}})

    assert response == {"result": {"items": []}}
    assert seen["url"].endswith("/v3/product/list")
    assert seen["client_id"] == "client-1"
    assert seen["api_key"] == "seller-secret"


async def test_transport_blocks_write_without_confirmation_before_network() -> None:
    called = False

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={"ok": True})

    transport = MarketplaceTransport(
        MarketplaceCredentials(platform="ozon", api_key="seller-secret", client_id="client-1"),
        http_transport=httpx.MockTransport(handler),
    )

    with pytest.raises(PermissionError):
        await transport.call_operation("ReviewAPI_SendAnswer", {"text": "ok"})

    assert called is False


async def test_transport_retries_429_then_returns_success() -> None:
    attempts = 0
    sleeps = []

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"Retry-After": "0"}, json={"error": "limit"})
        return httpx.Response(200, json={"ok": True})

    async def sleeper(seconds: float) -> None:
        sleeps.append(seconds)

    transport = MarketplaceTransport(
        MarketplaceCredentials(platform="ozon", api_key="seller-secret", client_id="client-1"),
        http_transport=httpx.MockTransport(handler),
        sleep=sleeper,
    )

    response = await transport.call_operation("ProductAPI_GetProductList", {})

    assert response == {"ok": True}
    assert attempts == 2
    assert sleeps == [0]


async def test_transport_redacts_secret_from_error_body() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            500,
            json={"message": "api_key=seller-secret failed"},
        )

    transport = MarketplaceTransport(
        MarketplaceCredentials(platform="ozon", api_key="seller-secret", client_id="client-1"),
        http_transport=httpx.MockTransport(handler),
        max_attempts=1,
    )

    with pytest.raises(MarketplaceApiError) as exc:
        await transport.call_operation("ProductAPI_GetProductList", {})

    assert "seller-secret" not in str(exc.value)
    assert "[REDACTED]" in str(exc.value)


async def test_transport_supports_path_params_and_dry_run_without_network() -> None:
    called = False

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={"ok": True})

    transport = MarketplaceTransport(
        MarketplaceCredentials(platform="ym", api_key="ym-secret"),
        http_transport=httpx.MockTransport(handler),
    )

    response = await transport.call_operation(
        "YM_UpdateCampaignBids",
        {
            "campaign_id": 123,
            "bids": [{"sku": "SKU-1", "bid": 100}],
        },
        dry_run=True,
    )

    assert called is False
    assert response["dryRun"] is True
    assert response["method"] == "POST"
    assert response["url"] == "https://api.partner.market.yandex.ru/v2/campaigns/123/bids"
    assert response["safety"] == "write"
    assert response["payload"] == {"bids": [{"sku": "SKU-1", "bid": 100}]}
    assert "ym-secret" not in str(response)


async def test_transport_builds_yandex_market_get_with_path_params() -> None:
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers.get("Authorization")
        return httpx.Response(200, json={"status": "OK", "result": {"offers": []}})

    transport = MarketplaceTransport(
        MarketplaceCredentials(platform="ym", api_key="ym-secret"),
        http_transport=httpx.MockTransport(handler),
    )

    response = await transport.call_operation(
        "YM_GetOfferPrices",
        {"campaign_id": 321, "limit": 1},
    )

    assert response["status"] == "OK"
    assert seen["url"] == (
        "https://api.partner.market.yandex.ru/v2/campaigns/321/offer-prices?limit=1"
    )
    assert seen["authorization"] == "Bearer ym-secret"


async def test_transport_uses_wb_bearer_header_and_platform_base_url() -> None:
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers.get("Authorization")
        return httpx.Response(200, json={"cards": []})

    transport = MarketplaceTransport(
        MarketplaceCredentials(platform="wb", api_key="wb-secret"),
        http_transport=httpx.MockTransport(handler),
    )

    response = await transport.call_operation("WB_Content_GetCardsList", {"settings": {}})

    assert response == {"cards": []}
    assert seen["url"] == "https://content-api.wildberries.ru/content/v2/get/cards/list"
    assert seen["authorization"] == "Bearer wb-secret"
