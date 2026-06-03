from operator_day.connectors.catalog import operation_catalog
from vendor.marketplace_sdk import (
    ozon_price_import,
    ozon_review_answer,
    wb_price_upload,
    wb_question_answer,
    yandex_market_bid_update,
)


def test_vendored_sdk_builders_match_operation_catalog() -> None:
    catalog = operation_catalog()
    builders = [
        ozon_review_answer(review_id="r1", text="ok"),
        ozon_price_import(offer_id="sku1", price=999),
        wb_question_answer(question_id="q1", text="ok"),
        wb_price_upload(vendor_code="sku2", price=888),
        yandex_market_bid_update(campaign_id="123", offer_id="sku3", bid=50),
    ]

    for operation_id, payload in builders:
        assert operation_id in catalog
        assert payload


def test_vendored_sdk_builders_are_secret_free_payloads() -> None:
    operation_id, payload = yandex_market_bid_update(
        campaign_id="123",
        offer_id="sku",
        bid=42,
    )

    assert operation_id == "YM_UpdateCampaignBids"
    assert "token" not in str(payload).lower()
    assert payload["bids"][0]["bid"] == 42
