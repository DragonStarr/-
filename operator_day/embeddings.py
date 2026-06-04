from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

from operator_day.config import Settings
from operator_day.memory import local_embedding, normalize_memory_text
from operator_day.security import redact_secret


@dataclass(frozen=True)
class EmbeddingResult:
    model: str
    vector: list[float]
    provider: str
    used_fallback: bool


class EmbeddingService:
    def __init__(
        self,
        settings: Settings,
        client_factory: Callable[..., httpx.AsyncClient] | None = None,
    ) -> None:
        self.settings = settings
        self._client_factory = client_factory or httpx.AsyncClient

    async def embed(self, text: str) -> EmbeddingResult:
        normalized = normalize_memory_text(text)
        if self._should_call_remote():
            remote = await self._try_remote_embedding(normalized)
            if remote is not None:
                return remote
        return EmbeddingResult(
            model=f"{self.settings.embedding_model}:local-hash-fallback",
            vector=local_embedding(normalized, size=self.settings.embedding_vector_size),
            provider="local",
            used_fallback=True,
        )

    def _should_call_remote(self) -> bool:
        return (
            self.settings.embedding_provider.lower() in {"bge-m3-http", "openai-compatible"}
            and bool(self.settings.embedding_base_url)
        )

    async def _try_remote_embedding(self, text: str) -> EmbeddingResult | None:
        payload: dict[str, Any] = {
            "model": self.settings.embedding_model,
            "input": text,
        }
        headers = {"Content-Type": "application/json"}
        if self.settings.embedding_api_key:
            headers["Authorization"] = f"Bearer {self.settings.embedding_api_key}"
        try:
            async with self._client_factory(timeout=20) as client:
                response = await client.post(
                    f"{self.settings.embedding_base_url.rstrip('/')}/embeddings",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                body = response.json()
        except httpx.HTTPError:
            return None
        vector = _extract_embedding_vector(body)
        if not vector or len(vector) != self.settings.embedding_vector_size:
            return None
        return EmbeddingResult(
            model=redact_secret(str(body.get("model") or self.settings.embedding_model)),
            vector=vector,
            provider=self.settings.embedding_provider,
            used_fallback=False,
        )


def _extract_embedding_vector(body: dict[str, Any]) -> list[float]:
    data = body.get("data")
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict) and isinstance(first.get("embedding"), list):
            return _numbers(first["embedding"])
    if isinstance(body.get("embedding"), list):
        return _numbers(body["embedding"])
    return []


def _numbers(values: list[Any]) -> list[float]:
    rows: list[float] = []
    for value in values:
        try:
            rows.append(float(value))
        except (TypeError, ValueError):
            return []
    return rows
