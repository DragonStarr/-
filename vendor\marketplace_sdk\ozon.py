from __future__ import annotations


def ozon_review_answer(*, review_id: str, text: str) -> tuple[str, dict[str, object]]:
    return (
        "ReviewAPI_SendAnswer",
        {
            "review_id": review_id,
            "text": text,
        },
    )


def ozon_price_import(*, offer_id: str, price: float) -> tuple[str, dict[str, object]]:
    return (
        "ProductAPI_ImportPrices",
        {
            "prices": [
                {
                    "offer_id": offer_id,
                    "price": str(int(round(price))),
                    "currency_code": "RUB",
                    "auto_action_enabled": "UNKNOWN",
                }
            ]
        },
    )
