from __future__ import annotations

from operator_day.domain import ClaimDeadlineRule, Platform

OWNER_VERIFICATION_REQUIRED = "baseline_requires_owner_verification"

DEFAULT_CLAIM_DEADLINE_RULES: tuple[ClaimDeadlineRule, ...] = (
    ClaimDeadlineRule(
        platform=Platform.OZON,
        claim_type="lost_or_damaged",
        days=30,
        source_url="https://docs.ozon.ru/seller/",
        note=OWNER_VERIFICATION_REQUIRED,
    ),
    ClaimDeadlineRule(
        platform=Platform.WB,
        claim_type="lost_or_damaged",
        days=14,
        source_url="https://dev.wildberries.ru/",
        note=OWNER_VERIFICATION_REQUIRED,
    ),
    ClaimDeadlineRule(
        platform=Platform.YANDEX,
        claim_type="lost_or_damaged",
        days=30,
        source_url="https://yandex.ru/dev/market/partner-api/",
        note=OWNER_VERIFICATION_REQUIRED,
    ),
)


def default_claim_deadline_rules() -> tuple[ClaimDeadlineRule, ...]:
    return DEFAULT_CLAIM_DEADLINE_RULES


def requires_owner_verification(policy: ClaimDeadlineRule) -> bool:
    return OWNER_VERIFICATION_REQUIRED in policy.note
