from __future__ import annotations

from copy import deepcopy
from typing import Any

from operator_day.connectors.transport import MarketplaceTransport


async def fetch_ozon_last_id_pages(
    transport: MarketplaceTransport,
    operation_id: str,
    payload: dict[str, Any],
    *,
    max_items: int = 10_000,
    max_pages: int = 100,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    last_id = ""
    seen_cursors: set[str] = set()
    for _ in range(max_pages):
        request_payload = deepcopy(payload)
        request_payload["last_id"] = last_id
        response = await transport.call_operation(operation_id, request_payload)
        result = response.get("result", response)
        page_items = list(result.get("items") or [])
        next_cursor = str(result.get("last_id") or "")
        if next_cursor and next_cursor in seen_cursors:
            break
        if not page_items:
            break
        items.extend(page_items)
        if len(items) >= max_items:
            return items[:max_items]
        if not next_cursor:
            break
        seen_cursors.add(next_cursor)
        last_id = next_cursor
    return items
