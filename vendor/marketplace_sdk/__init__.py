"""Small local marketplace SDK snapshot.

The runtime uses these builders so marketplace write plans do not depend on
external repositories being reachable at runtime.
"""

from vendor.marketplace_sdk.ozon import ozon_price_import, ozon_review_answer
from vendor.marketplace_sdk.wb import wb_campaign_pause, wb_price_upload, wb_question_answer
from vendor.marketplace_sdk.yandex_market import yandex_market_bid_update

__all__ = [
    "ozon_price_import",
    "ozon_review_answer",
    "wb_campaign_pause",
    "wb_price_upload",
    "wb_question_answer",
    "yandex_market_bid_update",
]
