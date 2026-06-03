from __future__ import annotations

from dataclasses import dataclass

from operator_day.brain.llm import LlmResponse, LlmRouter
from operator_day.domain import ReviewSnapshot
from operator_day.security import redact_secret


@dataclass(frozen=True)
class ReviewDraft:
    answer: str
    model: str
    used_fallback: bool
    tokens_estimate: int


class ReviewDraftService:
    def __init__(self, router: LlmRouter) -> None:
        self.router = router

    async def draft_positive_answer(self, review: ReviewSnapshot) -> ReviewDraft:
        prompt = (
            "Сделай короткий ответ на отзыв покупателя для маркетплейса. "
            "Без обещаний скидок, без спорных фактов, до 45 слов. "
            f"Оценка: {review.rating}. "
            f"Текст отзыва: {redact_secret(review.text)}. "
            f"Вопрос покупателя: {redact_secret(review.buyer_question or '')}."
        )
        response: LlmResponse = await self.router.complete_json_safe(prompt, max_tokens=180)
        return ReviewDraft(
            answer=response.text.strip(),
            model=response.model,
            used_fallback=response.used_fallback,
            tokens_estimate=response.tokens_estimate,
        )
