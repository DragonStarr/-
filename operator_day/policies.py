from __future__ import annotations

from fastapi import HTTPException

from operator_day.domain import ActionRisk, ModuleId, Role, TaskAction, TenantContext

_WRITE_ROLES = {Role.OWNER, Role.MANAGER}
_PVZ_OPERATOR_MODULES = {ModuleId.PVZ, ModuleId.ACCOUNTING, ModuleId.ANTIFRAUD}


def ensure_can_confirm(ctx: TenantContext, task: TaskAction) -> None:
    if ctx.role == Role.SUPPORT:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    if ctx.role == Role.PVZ_OPERATOR and task.module_id not in _PVZ_OPERATOR_MODULES:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    if task.risk in {ActionRisk.CONFIRM, ActionRisk.HUMAN} and ctx.role not in _WRITE_ROLES:
        raise HTTPException(status_code=403, detail="Недостаточно прав")


def ensure_can_connect_account(ctx: TenantContext) -> None:
    if ctx.role != Role.OWNER:
        raise HTTPException(status_code=403, detail="Недостаточно прав")


def ensure_can_manage_pvz(ctx: TenantContext) -> None:
    if ctx.role not in {Role.OWNER, Role.MANAGER}:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
