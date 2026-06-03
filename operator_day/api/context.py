from __future__ import annotations

import re
from typing import Annotated

from fastapi import Header, HTTPException

from operator_day.domain import Role, TenantContext

_CONTEXT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")
_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$")


def _validate_context_id(value: str) -> str:
    if not _CONTEXT_ID.fullmatch(value):
        raise HTTPException(status_code=400, detail="Неверный контекст продавца")
    return value


async def get_tenant_context(
    x_tenant_id: Annotated[str, Header(alias="X-Tenant-Id")] = "demo-tenant",
    x_user_id: Annotated[str, Header(alias="X-User-Id")] = "api-demo",
    x_role: Annotated[str, Header(alias="X-Role")] = Role.OWNER.value,
) -> TenantContext:
    try:
        role = Role(x_role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Неверный контекст продавца") from exc
    return TenantContext(
        tenant_id=_validate_context_id(x_tenant_id),
        user_id=_validate_context_id(x_user_id),
        role=role,
    )


def normalize_idempotency_key(ctx: TenantContext, task_id: str, raw_key: str | None) -> str:
    key = raw_key or "default"
    if not _IDEMPOTENCY_KEY.fullmatch(key):
        raise HTTPException(status_code=400, detail="Неверный ключ повтора")
    return f"{ctx.user_id}:{task_id}:{key}"
