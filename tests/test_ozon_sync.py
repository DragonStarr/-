import httpx

from operator_day.connectors.ozon_sync import OzonCatalogSync
from operator_day.connectors.transport import MarketplaceCredentials, MarketplaceTransport


async def test_ozon_catalog_sync_normalizes_products() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "result": {
                    "items": [
                        {"product_id": 10, "offer_id": "SKU-10", "archived": False},
                    ],
                    "last_id": "",
                }
            },
        )

    transport = MarketplaceTransport(
        MarketplaceCredentials(platform="ozon", api_key="seller-secret", client_id="client-1"),
        http_transport=httpx.MockTransport(handler),
    )

    rows = await OzonCatalogSync(transport).load_product_index()

    assert rows == [
        {
            "product_id": "10",
            "offer_id": "SKU-10",
            "archived": False,
            "source": "ozon",
        }
    ]
