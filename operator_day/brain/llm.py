from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

from operator_day.config import Settings
from operator_day.security import redact_secret


@dataclass(frozen=True)
class LlmResponse:
    text: str
    model: str
    used_fallback: bool
    tokens_estimate: int


class LlmRouter:
    def __init__(
        self,
        settings: Settings,
        client_factory: Callable[..., httpx.AsyncClient] | None = None,
    ) -> None:
        self.settings = settings
        self._tokens_used = 0
        self._client_factory = client_factory or httpx.AsyncClient

    async def list_models(self) -> list[str]:
        headers = self._openai_headers()
        async with self._client_factory(timeout=15) as client:
            response = await client.get(
                f"{self.settings.freemodel_base_url}/models", headers=headers
            )
            if response.status_code >= 400:
                response = await client.get(
                    f"{self.settings.freemodel_fallback_base_url}/models",
                    headers=headers,
                )
            response.raise_for_status()
            body = response.json()
        return [item["id"] for item in body.get("data", []) if "id" in item]

    async def probe_model(self) -> bool:
        if not self.settings.freemodel_api_key:
            return False
        response = await self.complete_json_safe("Ответь одним словом: ok", max_tokens=8)
        return response.model == self.settings.freemodel_model and not response.used_fallback

    async def complete_json_safe(self, prompt: str, *, max_tokens: int = 500) -> LlmResponse:
        clean_prompt = redact_secret(prompt)
        requested_tokens = self._estimate_tokens(clean_prompt) + max_tokens
        if self._would_exceed_budget(requested_tokens):
            return LlmResponse(
                text=self._offline_answer(clean_prompt),
                model="budget-fallback",
                used_fallback=True,
                tokens_estimate=self._estimate_tokens(clean_prompt),
            )
        if not self.settings.freemodel_api_key:
            return LlmResponse(
                text=self._offline_answer(clean_prompt),
                model="offline-template",
                used_fallback=True,
                tokens_estimate=self._estimate_tokens(clean_prompt),
            )

        try:
            return await self._complete_responses(clean_prompt, max_tokens=max_tokens)
        except httpx.HTTPStatusError:
            pass
        return await self._complete_openai_chat(clean_prompt, max_tokens=max_tokens)

    async def _complete_responses(self, prompt: str, *, max_tokens: int) -> LlmResponse:
        payload: dict[str, Any] = {
            "model": self.settings.freemodel_model,
            "instructions": (
                "Пиши коротко, простым русским языком. "
                "Не выдумывай факты. Если данных мало, скажи это."
            ),
            "input": prompt,
            "max_output_tokens": max_tokens,
            "temperature": 0.2,
        }
        async with self._client_factory(timeout=30) as client:
            response = await client.post(
                f"{self.settings.freemodel_base_url}/responses",
                headers=self._openai_headers(),
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
        text = _responses_text(body)
        usage = body.get("usage", {})
        tokens_estimate = int(usage.get("total_tokens") or self._estimate_tokens(prompt))
        self._tokens_used += tokens_estimate
        actual_model = str(body.get("model") or self.settings.freemodel_model)
        used_fallback = actual_model != self.settings.freemodel_model
        return LlmResponse(
            text=redact_secret(text),
            model=actual_model,
            used_fallback=used_fallback,
            tokens_estimate=tokens_estimate,
        )

    async def _complete_openai_chat(self, prompt: str, *, max_tokens: int) -> LlmResponse:
        payload: dict[str, Any] = {
            "model": self.settings.freemodel_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Пиши коротко, простым русским языком. "
                        "Не выдумывай факты. Если данных мало, скажи это."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }
        headers = self._openai_headers()
        async with self._client_factory(timeout=30) as client:
            response = await client.post(
                f"{self.settings.freemodel_base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            used_fallback = False
            if response.status_code >= 400:
                response = await client.post(
                    f"{self.settings.freemodel_fallback_base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                used_fallback = True
            response.raise_for_status()
            body = response.json()
        text = body["choices"][0]["message"]["content"]
        usage = body.get("usage", {})
        tokens_estimate = int(usage.get("total_tokens") or self._estimate_tokens(prompt))
        self._tokens_used += tokens_estimate
        return LlmResponse(
            text=redact_secret(text),
            model=self.settings.freemodel_model,
            used_fallback=used_fallback,
            tokens_estimate=tokens_estimate,
        )

    def _openai_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.settings.freemodel_api_key:
            headers["Authorization"] = f"Bearer {self.settings.freemodel_api_key}"
        return headers

    @staticmethod
    def _offline_answer(prompt: str) -> str:
        if "ответ на отзыв" in prompt.lower() or "отзыв" in prompt.lower():
            return (
                "Спасибо за отзыв. Мы рады, что товар вам понравился. "
                "Если появятся вопросы, напишите нам."
            )
        return "Данные собраны. Я подготовил безопасный черновик, проверьте и нажмите ОК."

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return max(1, int(len(text.split()) * 1.35))

    def _would_exceed_budget(self, requested_tokens: int) -> bool:
        budget = self.settings.llm_daily_token_budget
        return budget > 0 and self._tokens_used + requested_tokens > budget


def _responses_text(body: dict[str, Any]) -> str:
    output_text = body.get("output_text")
    if isinstance(output_text, str) and output_text:
        return output_text
    outputs = body.get("output") or []
    parts: list[str] = []
    for item in outputs:
        if not isinstance(item, dict):
            continue
        for block in item.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "output_text":
                parts.append(str(block.get("text") or ""))
    return "\n".join(part for part in parts if part)
