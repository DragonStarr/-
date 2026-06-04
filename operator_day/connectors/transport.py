from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import httpx

from operator_day.connectors.catalog import operation_catalog
from operator_day.connectors.safety import (
    MarketplaceOperation,
    OperationSafety,
    ensure_operation_allowed,
)
from operator_day.security import redact_secret

SleepFn = Callable[[float], Awaitable[None]]

_BASE_URLS = {
    "ozon": "https://api-seller.ozon.ru",
    "ozon_performance": "https://api-performance.ozon.ru",
    "wb": "https://common-api.wildberries.ru",
    "yandex_market": "https://api.partner.market.yandex.ru",
}

_PATH_PARAM = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
_GLOBAL_RATE_BUCKETS: dict[str, _RateBucket] = {}


class MarketplaceApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class MarketplaceCredentials:
    platform: str
    api_key: str
    client_id: str = ""
    access_token: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class _RateBucket:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    next_at: float = 0.0


class MarketplaceTransport:
    def __init__(
        self,
        credentials: MarketplaceCredentials,
        *,
        http_transport: httpx.AsyncBaseTransport | None = None,
        sleep: SleepFn = asyncio.sleep,
        max_attempts: int = 3,
    ) -> None:
        self.credentials = credentials
        self.http_transport = http_transport
        self.sleep = sleep
        self.max_attempts = max_attempts
        self.operations = operation_catalog()

    async def call_operation(
        self,
        operation_id: str,
        payload: dict[str, Any],
        *,
        confirm_write: bool = False,
        confirm_destructive: bool = False,
        dry_run: bool = False,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        operation = self.operations[operation_id]
        if not dry_run:
            ensure_operation_allowed(
                operation,
                confirm_write=confirm_write,
                confirm_destructive=confirm_destructive,
            )
        url, request_payload = self._build_request(operation, payload)
        if dry_run:
            return {
                "dryRun": True,
                "operationId": operation.operation_id,
                "platform": operation.platform,
                "method": operation.method.upper(),
                "url": url,
                "safety": operation.safety.value,
                "rateLimitKey": operation.rate_limit_key,
                "subscriptionTier": operation.subscription_tier,
                "idempotencyKey": idempotency_key,
                "payload": request_payload,
            }
        headers = self._headers(operation.platform)
        if operation.safety != OperationSafety.READ and idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key
        await self._respect_rate_limit(operation)
        async with httpx.AsyncClient(
            transport=self.http_transport,
            timeout=30,
        ) as client:
            for attempt in range(1, self.max_attempts + 1):
                response = await self._send(client, operation.method, url, headers, request_payload)
                if response.status_code < 400:
                    return response.json()
                retry_allowed = operation.safety == OperationSafety.READ or bool(idempotency_key)
                if (
                    not retry_allowed
                    or not self._should_retry(response.status_code)
                    or attempt == self.max_attempts
                ):
                    raise self._error(operation_id, response)
                await self.sleep(self._retry_delay(response, attempt))
        raise MarketplaceApiError(f"{operation_id}: unexpected transport state")

    async def _send(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> httpx.Response:
        if method.upper() == "GET":
            return await client.get(url, headers=headers, params=payload)
        if method.upper() == "PATCH":
            return await client.patch(url, headers=headers, json=payload)
        if method.upper() == "PUT":
            return await client.put(url, headers=headers, json=payload)
        if method.upper() == "DELETE":
            return await client.delete(url, headers=headers, json=payload)
        return await client.post(url, headers=headers, json=payload)

    def _headers(self, platform: str) -> dict[str, str]:
        if platform == "ozon":
            return {
                "Client-Id": self.credentials.client_id,
                "Api-Key": self.credentials.api_key,
                "Content-Type": "application/json",
            }
        if platform == "wb":
            return {
                "Authorization": f"Bearer {self.credentials.api_key}",
                "Content-Type": "application/json",
            }
        if platform == "yandex_market":
            token = self.credentials.access_token or self.credentials.api_key
            return {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
        if self.credentials.access_token:
            return {"Authorization": f"Bearer {self.credentials.access_token}"}
        return {
            "Client-Id": self.credentials.client_id,
            "Client-Secret": self.credentials.api_key,
            "Content-Type": "application/json",
        }

    @staticmethod
    def _should_retry(status_code: int) -> bool:
        return status_code in {420, 429} or 500 <= status_code < 600

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(0, float(retry_after))
            except ValueError:
                return 1
        return min(30, 2 ** (attempt - 1))

    def _error(self, operation_id: str, response: httpx.Response) -> MarketplaceApiError:
        raw = response.text
        raw = raw.replace(self.credentials.api_key, "[REDACTED]")
        if self.credentials.client_id:
            raw = raw.replace(self.credentials.client_id, "[REDACTED]")
        if self.credentials.access_token:
            raw = raw.replace(self.credentials.access_token, "[REDACTED]")
        return MarketplaceApiError(
            redact_secret(
                f"{operation_id}: marketplace API error {response.status_code}: {raw}"
            )
        )

    def _build_request(
        self,
        operation: MarketplaceOperation,
        payload: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        request_payload = dict(payload)
        endpoint = operation.endpoint
        for name in _PATH_PARAM.findall(endpoint):
            if name not in request_payload:
                raise ValueError(f"{operation.operation_id}: missing path parameter {name}")
            raw_value = request_payload.pop(name)
            endpoint = endpoint.replace("{" + name + "}", quote(str(raw_value), safe=""))
        base_url = operation.base_url or _BASE_URLS[operation.platform]
        return f"{base_url}{endpoint}", request_payload

    async def _respect_rate_limit(self, operation: MarketplaceOperation) -> None:
        rate_limit_key = operation.rate_limit_key
        if not rate_limit_key:
            return
        bucket = _GLOBAL_RATE_BUCKETS.setdefault(rate_limit_key, _RateBucket())
        async with bucket.lock:
            now = time.monotonic()
            delay = bucket.next_at - now
            if delay > 0:
                await self.sleep(delay)
                now = time.monotonic()
            bucket.next_at = max(bucket.next_at, now) + max(
                operation.rate_limit_interval_seconds,
                0,
            )
