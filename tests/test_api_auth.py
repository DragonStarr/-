from __future__ import annotations

import hashlib
import hmac
import json
from urllib.parse import urlencode

from httpx import ASGITransport, AsyncClient

from operator_day.config import get_settings
from operator_day.domain import Role, TenantContext
from operator_day.main import create_app
from operator_day.security import create_session_token


def _prod_env(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ALLOW_DEMO_AUTH", "false")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://operator:test@localhost/db")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "6vYyVj6AIcfVt24EsVSIx3JEXxHFsnvpa4tbfoAeTPk=")
    monkeypatch.setenv("APP_SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:telegram-token-for-test")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "webhook-secret")
    get_settings.cache_clear()


async def test_api_rejects_raw_context_headers_outside_local(monkeypatch) -> None:
    _prod_env(monkeypatch)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=create_app()), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/brain/llm-status",
                headers={
                    "X-Tenant-Id": "victim",
                    "X-User-Id": "attacker",
                    "X-Role": "owner",
                },
            )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 401


async def test_api_accepts_signed_session_outside_local(monkeypatch) -> None:
    _prod_env(monkeypatch)
    token = create_session_token(
        TenantContext("seller-prod", "owner-prod", Role.OWNER),
        "test-session-secret",
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=create_app()), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/brain/llm-status",
                headers={"Authorization": f"Bearer {token}"},
            )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    assert response.json()["status"] in {"configured", "not_configured"}


async def test_telegram_auth_endpoint_issues_session(monkeypatch) -> None:
    _prod_env(monkeypatch)
    init_data = _signed_init_data(
        "123456:telegram-token-for-test",
        {"id": 777, "first_name": "Мария"},
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=create_app()), base_url="http://test"
        ) as client:
            auth = await client.post(
                "/api/auth/telegram",
                json={"initData": init_data},
            )
            token = auth.json()["accessToken"]
            status = await client.get(
                "/api/brain/llm-status",
                headers={"Authorization": f"Bearer {token}"},
            )
    finally:
        get_settings.cache_clear()

    assert auth.status_code == 200
    assert auth.json()["tenantId"] == "tg-777"
    assert status.status_code == 200


def _signed_init_data(bot_token: str, user: dict) -> str:
    values = {
        "auth_date": "1790000000",
        "query_id": "query-1",
        "user": json.dumps(user, separators=(",", ":")),
    }
    data_check = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    signature = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    return urlencode({**values, "hash": signature})
