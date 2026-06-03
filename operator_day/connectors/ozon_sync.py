from __future__ import annotations

from operator_day.connectors.pagination import fetch_ozon_last_id_pages
from operator_day.connectors.transport import MarketplaceTransport


class OzonCatalogSync:
    def __init__(self, transport: MarketplaceTransport) -> None:
        self.transport = transport

    async def load_product_index(self) -> list[dict]:
        items = await fetch_ozon_last_id_pages(
            self.transport,
            "ProductAPI_GetProductList",
            {"filter": {"visibility": "ALL"}, "limit": 1000},
        )
        return [
            {
                "product_id": str(item.get("product_id", "")),
                "offer_id": str(item.get("offer_id", "")),
                "archived": bool(item.get("archived", False)),
                "source": "ozon",
            }
            for item in items
        ]
