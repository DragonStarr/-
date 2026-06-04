from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class Platform(StrEnum):
    WB = "wb"
    OZON = "ozon"
    YANDEX = "ym"
    PVZ = "pvz"


class Role(StrEnum):
    OWNER = "owner"
    MANAGER = "manager"
    PVZ_OPERATOR = "pvz_operator"
    SUPPORT = "support"


class TaskStatus(StrEnum):
    NEW = "new"
    WAITING_CONFIRMATION = "waiting_confirmation"
    PLANNED = "planned"
    DONE = "done"
    ESCALATED = "escalated"
    FAILED = "failed"


class ActionRisk(StrEnum):
    SAFE = "safe"
    CONFIRM = "confirm"
    HUMAN = "human"


class ModuleId(StrEnum):
    ACCOUNTS = "M01_ACCOUNTS"
    UNIT = "M02_UNIT"
    SEO = "M03_SEO"
    SUPPLIES = "M04_SUPPLIES"
    REVIEWS = "M05_REVIEWS"
    COMPETITORS = "M06_COMPETITORS"
    REPRICER = "M07_REPRICER"
    FINANCE = "M08_FINANCE"
    ANTIFRAUD = "M09_ANTIFRAUD"
    FORECAST = "M10_FORECAST"
    PVZ = "M11_PVZ"
    RULES = "M12_RULES"
    MORNING = "M13_MORNING"
    ACCOUNTING = "M14_ACCOUNTING"
    BILLING = "M15_BILLING"
    SUPERVISOR = "M16_SUPERVISOR"
    LEARNING = "M17_LEARNING"
    RADAR = "M18_RADAR"
    ADS = "M19_ADS"
    CLAIMS = "M20_CLAIMS"
    NICHES = "M21_NICHES"
    CONTENT = "M22_CONTENT"
    ACCOUNT_GUARD = "M23_ACCOUNT_GUARD"


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    user_id: str
    role: Role
    timezone: str = "Europe/Moscow"


@dataclass(frozen=True)
class ProductSnapshot:
    platform: Platform
    sku: str
    name: str
    price: float
    stock: int | None
    cost: float
    commission_rate: float
    rating: float = 0
    daily_sales: float | None = None
    data_sources: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ReviewSnapshot:
    platform: Platform
    review_id: str
    sku: str
    rating: int
    text: str
    buyer_question: str | None = None


@dataclass(frozen=True)
class ClaimDeadlineRule:
    platform: Platform
    claim_type: str
    days: int
    source_url: str
    note: str = ""


@dataclass(frozen=True)
class ClaimCandidate:
    platform: Platform
    claim_id: str
    claim_type: str
    sku: str
    amount: float
    reason: str
    evidence: tuple[str, ...]
    discovered_at: datetime
    source: str = ""


@dataclass(frozen=True)
class PvzEmployee:
    employee_id: str
    name: str
    hourly_rate: float
    preferred_days: tuple[int, ...] = ()


@dataclass(frozen=True)
class PvzPoint:
    point_id: str
    title: str
    monthly_turnover: float
    employees: tuple[PvzEmployee, ...]


@dataclass(frozen=True)
class ModuleSignal:
    module_id: ModuleId
    title: str
    reason: str
    priority: int
    payload: dict[str, Any] = field(default_factory=dict)
    risk: ActionRisk = ActionRisk.SAFE


@dataclass
class TaskAction:
    module_id: ModuleId
    title: str
    short_text: str
    action_label: str
    payload: dict[str, Any]
    priority: int
    risk: ActionRisk
    money_effect: float = 0
    urgency: float = 0.1
    confidence: float = 0.7
    deadline_at: datetime | None = None
    score: float = 0
    task_id: str = field(default_factory=lambda: str(uuid4()))
    status: TaskStatus = TaskStatus.NEW
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def confirm_required(self) -> bool:
        return self.risk in {ActionRisk.CONFIRM, ActionRisk.HUMAN}

    def has_near_deadline(self) -> bool:
        if self.deadline_at is None:
            return False
        delta = self.deadline_at - datetime.now(UTC)
        return delta.total_seconds() <= 24 * 60 * 60


@dataclass(frozen=True)
class ActionResult:
    task_id: str
    status: TaskStatus
    user_text: str
    audit_event: dict[str, Any]


@dataclass(frozen=True)
class ConnectedAccount:
    account_id: str
    platform: Platform
    title: str
    status: str
    token_fingerprint: str
    capabilities: dict[str, str]
    limitations: tuple[str, ...] = ()
