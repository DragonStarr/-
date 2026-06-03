from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TaskOut(BaseModel):
    task_id: str = Field(alias="taskId")
    module_id: str = Field(alias="moduleId")
    title: str
    short_text: str = Field(alias="shortText")
    action_label: str = Field(alias="actionLabel")
    priority: int
    risk: str
    status: str
    score: float
    money_effect: float = Field(alias="moneyEffect")
    confidence: float
    deadline_at: str | None = Field(alias="deadlineAt")
    payload: dict[str, Any]


class FeedbackIn(BaseModel):
    task_id: str = Field(alias="taskId")
    score: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=2000)


class ConfirmOut(BaseModel):
    task_id: str = Field(alias="taskId")
    status: str
    text: str
    audit_event: dict[str, Any] = Field(alias="auditEvent")


class AccountIn(BaseModel):
    platform: str = Field(pattern="^(wb|ozon|ym|pvz)$")
    title: str = Field(min_length=1, max_length=200)
    api_key: str = Field(alias="apiKey", min_length=8, max_length=4000)
    client_id: str | None = Field(default=None, alias="clientId", max_length=200)
    performance_client_id: str | None = Field(
        default=None,
        alias="performanceClientId",
        max_length=200,
    )
    performance_client_secret: str | None = Field(
        default=None,
        alias="performanceClientSecret",
        max_length=4000,
    )
    campaign_id: str | None = Field(default=None, alias="campaignId", max_length=80)
    business_id: str | None = Field(default=None, alias="businessId", max_length=80)


class AccountOut(BaseModel):
    account_id: str = Field(alias="accountId")
    platform: str
    title: str
    status: str
    token_fingerprint: str = Field(alias="tokenFingerprint")
    capabilities: dict[str, str]
    limitations: tuple[str, ...]


class CapabilityOut(BaseModel):
    account_id: str = Field(alias="accountId")
    platform: str
    title: str
    capabilities: dict[str, str]
    limitations: tuple[str, ...]


class ArchitectureReviewOut(BaseModel):
    text: str
    model: str
    used_fallback: bool = Field(alias="usedFallback")
    tokens_estimate: int = Field(alias="tokensEstimate")


class ArchitectureGateOut(BaseModel):
    topology: dict[str, Any]
    verdict: str
    text: str
    blockers: tuple[str, ...]
    model: str
    used_fallback: bool = Field(alias="usedFallback")
    tokens_estimate: int = Field(alias="tokensEstimate")


class LlmStatusOut(BaseModel):
    configured: bool
    model: str
    primary_provider: str = Field(alias="primaryProvider")
    primary_model: str = Field(alias="primaryModel")
    external_enabled: bool = Field(alias="externalEnabled")
    smoke_enabled: bool = Field(alias="smokeEnabled")
    live_check_requested: bool = Field(alias="liveCheckRequested")
    live_check_ran: bool = Field(alias="liveCheckRan")
    model_available: bool | None = Field(alias="modelAvailable")
    status: str


class ClaimDeadlineIn(BaseModel):
    platform: str = Field(pattern="^(wb|ozon|ym)$")
    claim_type: str = Field(alias="claimType", min_length=1, max_length=120)
    days: int = Field(ge=1, le=365)
    source_url: str = Field(alias="sourceUrl", min_length=10, max_length=1000)
    note: str = Field(default="", max_length=2000)


class ClaimDeadlineOut(BaseModel):
    policy_id: str = Field(alias="policyId")
    platform: str
    claim_type: str = Field(alias="claimType")
    days: int
    source_url: str = Field(alias="sourceUrl")
    note: str


class ClaimCandidateIn(BaseModel):
    platform: str = Field(pattern="^(wb|ozon|ym)$")
    claim_id: str | None = Field(default=None, alias="claimId", max_length=120)
    claim_type: str = Field(alias="claimType", min_length=1, max_length=120)
    sku: str = Field(min_length=1, max_length=120)
    amount: float = Field(gt=0)
    reason: str = Field(min_length=1, max_length=1000)
    evidence: list[str] = Field(min_length=1, max_length=20)
    discovered_at: datetime = Field(alias="discoveredAt")
    source: str = Field(default="manual", min_length=1, max_length=120)


class ClaimsImportIn(BaseModel):
    claims: list[ClaimCandidateIn] = Field(min_length=1, max_length=1000)


class ClaimsImportOut(BaseModel):
    count: int


class PvzEmployeeIn(BaseModel):
    employee_id: str | None = Field(default=None, alias="employeeId", max_length=120)
    name: str = Field(min_length=1, max_length=200)
    hourly_rate: float = Field(alias="hourlyRate", gt=0)
    preferred_days: list[int] = Field(default_factory=list, alias="preferredDays", max_length=7)


class PvzPointIn(BaseModel):
    point_id: str | None = Field(default=None, alias="pointId", max_length=120)
    title: str = Field(min_length=1, max_length=300)
    monthly_turnover: float = Field(default=0, alias="monthlyTurnover", ge=0)
    employees: list[PvzEmployeeIn] = Field(min_length=1, max_length=100)
    source: str = Field(default="manual", min_length=1, max_length=120)


class PvzImportIn(BaseModel):
    points: list[PvzPointIn] = Field(min_length=1, max_length=100)


class PvzImportOut(BaseModel):
    count: int


class ReviewImportItemIn(BaseModel):
    platform: str = Field(pattern="^(wb|ozon|ym)$")
    review_id: str | None = Field(default=None, alias="reviewId", max_length=120)
    sku: str = Field(min_length=1, max_length=120)
    rating: int = Field(ge=1, le=5)
    text: str = Field(min_length=1, max_length=5000)
    buyer_question: str | None = Field(default=None, alias="buyerQuestion", max_length=2000)
    answer_status: str = Field(default="new", alias="answerStatus", max_length=32)
    source: str = Field(default="manual", min_length=1, max_length=120)


class ReviewsImportIn(BaseModel):
    reviews: list[ReviewImportItemIn] = Field(min_length=1, max_length=1000)


class ReviewsImportOut(BaseModel):
    count: int


class CatalogProductIn(BaseModel):
    sku: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=500)
    price: float = Field(default=0, ge=0)
    cost: float = Field(default=0, ge=0)


class CatalogImportIn(BaseModel):
    account_id: str = Field(alias="accountId", min_length=1, max_length=64)
    source: str = Field(default="manual", min_length=1, max_length=120)
    products: list[CatalogProductIn] = Field(min_length=1, max_length=1000)


class CatalogImportOut(BaseModel):
    account_id: str = Field(alias="accountId")
    source: str
    count: int


class SyncCatalogIn(BaseModel):
    dry_run: bool = Field(default=True, alias="dryRun")


class SyncCatalogOut(BaseModel):
    account_id: str = Field(alias="accountId")
    source: str
    dry_run: bool = Field(alias="dryRun")
    count: int
    planned_operation: dict[str, Any] | None = Field(default=None, alias="plannedOperation")


class ValidateAccountIn(BaseModel):
    dry_run: bool = Field(default=True, alias="dryRun")


class ValidateAccountOut(BaseModel):
    account_id: str = Field(alias="accountId")
    source: str
    status: str
    dry_run: bool = Field(alias="dryRun")
    planned_operation: dict[str, Any] | None = Field(default=None, alias="plannedOperation")


class PluginManifestIn(BaseModel):
    id: str = Field(min_length=3, max_length=80)
    label: str = Field(min_length=2, max_length=80)
    surface: str = Field(default="both")
    module_id: str = Field(alias="moduleId", min_length=2, max_length=20)
    action: str = Field(min_length=3, max_length=80)
    input_schema: dict[str, Any] = Field(default_factory=dict, alias="inputSchema")
    scopes: list[str] = Field(default_factory=list, max_length=20)
    required_role: str = Field(default="owner", alias="requiredRole")
    requires_confirm: bool = Field(default=True, alias="requiresConfirm")
    activate: bool = False


class PluginManifestOut(BaseModel):
    plugin_id: str = Field(alias="pluginId")
    label: str
    surface: str
    module_id: str = Field(alias="moduleId")
    action: str
    status: str
    requires_confirm: bool = Field(alias="requiresConfirm")
    input_schema: dict[str, Any] = Field(alias="inputSchema")


class SelfUpdatePlanIn(BaseModel):
    source: str = Field(min_length=10, max_length=500)
    current_snapshot: str = Field(default="vendor/_snapshots/current", alias="currentSnapshot")


class SelfUpdateRunIn(BaseModel):
    source: str = Field(min_length=10, max_length=500)
    diff_text: str = Field(default="", alias="diffText", max_length=12000)


class SelfUpdateOut(BaseModel):
    run_id: str | None = Field(default=None, alias="runId")
    source: str
    current_snapshot: str = Field(alias="currentSnapshot")
    candidate_snapshot: str = Field(alias="candidateSnapshot")
    status: str
    gates: dict[str, str]
    notes: list[str]
