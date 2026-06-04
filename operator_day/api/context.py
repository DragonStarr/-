from __future__ import annotations

import re
from typing import Annotated

from fastapi import Header, HTTPException

from operator_day.config import get_settings
from operator_day.db import ensure_local_database, get_sessionmaker
from operator_day.domain import Role, TenantContext
from operator_day.repositories import UserRepository
from operator_day.security import (
    AuthError,
    telegram_identity_from_init_data,
    verify_session_token,
    verify_telegram_init_data,
)

_CONTEXT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")
_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$")


def _validate_context_id(value: str) -> str:
    if not _CONTEXT_ID.fullmatch(value):
        raise HTTPException(status_code=400, detail="Неверный контекст продавца")
    return value


async def get_tenant_context(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    x_telegram_init_data: Annotated[
        str | None,
        Header(alias="X-Telegram-Init-Data"),
    ] = None,
    x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-Id")] = None,
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> TenantContext:
    settings = get_settings()
    bearer = _bearer_token(authorization)
    try:
        if bearer:
            return verify_session_token(bearer, settings.app_session_secret)
        if x_telegram_init_data:
            values = verify_telegram_init_data(
                x_telegram_init_data,
                settings.telegram_bot_token,
                ttl_seconds=settings.telegram_web_app_auth_ttl_seconds,
            )
            tg_id, name = telegram_identity_from_init_data(values)
            await ensure_local_database()
            async with get_sessionmaker()() as session:
                return await UserRepository(session).context_for_telegram(tg_id, name)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail="Invalid API auth") from exc

    if not (settings.is_local_env() and settings.allow_demo_auth):
        raise HTTPException(status_code=401, detail="API auth is required")

    role_value = x_role or Role.OWNER.value
    try:
        role = Role(role_value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Неверный контекст продавца") from exc
    return TenantContext(
        tenant_id=_validate_context_id(x_tenant_id or "demo-tenant"),
        user_id=_validate_context_id(x_user_id or "api-demo"),
        role=role,
    )


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid bearer token")
    return token.strip()


def normalize_idempotency_key(ctx: TenantContext, task_id: str, raw_key: str | None) -> str:
    key = raw_key or "default"
    if not _IDEMPOTENCY_KEY.fullmatch(key):
        raise HTTPException(status_code=400, detail="Неверный ключ повтора")
    return f"{ctx.user_id}:{task_id}:{key}"
