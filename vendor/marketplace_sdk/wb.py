from __future__ import annotations


def wb_question_answer(*, question_id: str, text: str) -> tuple[str, dict[str, object]]:
    return (
        "WB_Questions_PatchAnswer",
        {
            "id": question_id,
            "text": text,
        },
    )


def wb_price_upload(*, vendor_code: str, price: float) -> tuple[str, dict[str, object]]:
    return (
        "WB_Prices_UploadTask",
        {
            "data": [
                {
                    "vendorCode": vendor_code,
                    "price": int(round(price)),
                }
            ]
        },
    )


def wb_campaign_pause(*, campaign_id: str) -> tuple[str, dict[str, object]]:
    return (
        "WB_Promotion_PauseCampaign",
        {
            "id": int(campaign_id) if str(campaign_id).isdigit() else campaign_id,
        },
    )
