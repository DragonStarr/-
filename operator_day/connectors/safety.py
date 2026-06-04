from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class OperationSafety(StrEnum):
    READ = "read"
    WRITE = "write"
    DESTRUCTIVE = "destructive"


@dataclass(frozen=True)
class MarketplaceOperation:
    operation_id: str
    platform: str
    safety: OperationSafety
    method: str = "POST"
    endpoint: str = ""
    base_url: str = ""
    rate_limit_key: str = ""
    rate_limit_interval_seconds: float = 0.05
    subscription_tier: str = ""


def ensure_operation_allowed(
    operation: MarketplaceOperation,
    *,
    confirm_write: bool = False,
    confirm_destructive: bool = False,
) -> None:
    if operation.safety == OperationSafety.READ:
        return
    if operation.safety == OperationSafety.WRITE and confirm_write:
        return
    if (
        operation.safety == OperationSafety.DESTRUCTIVE
        and confirm_write
        and confirm_destructive
    ):
        return
    if operation.safety == OperationSafety.DESTRUCTIVE:
        raise PermissionError("destructive operation requires double confirmation")
    raise PermissionError("write operation requires confirm_write")
