from __future__ import annotations


def yandex_market_bid_update(
    *,
    business_id: str,
    offer_id: str,
    bid: int,
) -> tuple[str, dict[str, object]]:
    return (
        "YM_UpdateCampaignBids",
        {
            "business_id": business_id,
            "bids": [
                {
                    "offerId": offer_id,
                    "bid": max(int(bid), 0),
                }
            ],
        },
    )
