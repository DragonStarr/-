from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TenantBound:
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(String(200))
    plan: Mapped[str] = mapped_column(String(64), default="safe_test")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base, TenantBound):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    tg_id: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(200), default="")


class Account(Base, TenantBound):
    __tablename__ = "accounts"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    platform: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    token_enc: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="new")
    token_fingerprint: Mapped[str] = mapped_column(String(32), default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class Product(Base, TenantBound):
    __tablename__ = "products"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    sku: Mapped[str] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(500))
    category: Mapped[str] = mapped_column(String(200), default="")
    price: Mapped[float] = mapped_column(Float)
    cost: Mapped[float] = mapped_column(Float, default=0)
    commission_rate: Mapped[float] = mapped_column(Float, default=0)
    rating: Mapped[float] = mapped_column(Float, default=0)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class Stock(Base, TenantBound):
    __tablename__ = "stocks"
    __table_args__ = (
        UniqueConstraint("tenant_id", "product_id", "warehouse", name="uq_stock_product_warehouse"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    warehouse: Mapped[str] = mapped_column(String(200), default="")
    quantity: Mapped[int] = mapped_column(Integer)


class Sale(Base, TenantBound):
    __tablename__ = "sales"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    account_id: Mapped[str] = mapped_column(String(64), index=True, default="")
    platform: Mapped[str] = mapped_column(String(32), index=True)
    sku: Mapped[str] = mapped_column(String(120), index=True)
    sold_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    revenue: Mapped[float] = mapped_column(Float, default=0)
    cost: Mapped[float] = mapped_column(Float, default=0)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Review(Base, TenantBound):
    __tablename__ = "reviews"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(32), default="ozon", index=True)
    rating: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    answer_status: Mapped[str] = mapped_column(String(32), default="new")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class Task(Base, TenantBound):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    module_id: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(500))
    short_text: Mapped[str] = mapped_column(Text)
    action_label: Mapped[str] = mapped_column(String(160))
    risk: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    priority: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float, default=0)
    money_effect: Mapped[float] = mapped_column(Float, default=0)
    urgency: Mapped[float] = mapped_column(Float, default=0.1)
    confidence: Mapped[float] = mapped_column(Float, default=0.7)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Feedback(Base, TenantBound):
    __tablename__ = "feedback"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    task_id: Mapped[str] = mapped_column(String(64), index=True)
    score: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str] = mapped_column(Text, default="")


class AuditLog(Base, TenantBound):
    __tablename__ = "audit_log"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(100))
    before_after: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ActionExecution(Base, TenantBound):
    __tablename__ = "action_executions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "task_id", "idempotency_key", name="uq_action_idempotency"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    task_id: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class JsonTenantRecord(Base, TenantBound):
    __abstract__ = True

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    product_id: Mapped[str] = mapped_column(String(64), index=True, default="")
    source: Mapped[str] = mapped_column(String(120), default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SeoQuery(JsonTenantRecord):
    __tablename__ = "seo_queries"


class SeoDraft(JsonTenantRecord):
    __tablename__ = "seo_drafts"


class KeywordPosition(JsonTenantRecord):
    __tablename__ = "keyword_positions"


class KeywordFrequency(JsonTenantRecord):
    __tablename__ = "keyword_freq"


class CompetitorKeyword(JsonTenantRecord):
    __tablename__ = "competitor_keywords"


class ReviewAspect(JsonTenantRecord):
    __tablename__ = "review_aspects"


class CogsBatch(JsonTenantRecord):
    __tablename__ = "cogs_batches"


class WarehouseDistribution(JsonTenantRecord):
    __tablename__ = "warehouse_distribution"


class TokenUsage(JsonTenantRecord):
    __tablename__ = "token_usage"


class AdCampaign(JsonTenantRecord):
    __tablename__ = "ad_campaigns"


class AdKeyword(JsonTenantRecord):
    __tablename__ = "ad_keywords"


class BidRule(JsonTenantRecord):
    __tablename__ = "bid_rules"


class BidHistory(JsonTenantRecord):
    __tablename__ = "bid_history"


class CompetitorBid(JsonTenantRecord):
    __tablename__ = "competitor_bids"


class KeywordCluster(JsonTenantRecord):
    __tablename__ = "keyword_clusters"


class Claim(JsonTenantRecord):
    __tablename__ = "claims"


class ClaimItem(JsonTenantRecord):
    __tablename__ = "claim_items"


class LostDamaged(JsonTenantRecord):
    __tablename__ = "lost_damaged"


class Reconciliation(JsonTenantRecord):
    __tablename__ = "reconciliations"


class ClaimDeadlinePolicy(Base, TenantBound):
    __tablename__ = "claim_deadline_policies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    platform: Mapped[str] = mapped_column(String(32), index=True)
    claim_type: Mapped[str] = mapped_column(String(120), index=True)
    days: Mapped[int] = mapped_column(Integer)
    source_url: Mapped[str] = mapped_column(String(1000))
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Niche(JsonTenantRecord):
    __tablename__ = "niches"


class NicheMetric(JsonTenantRecord):
    __tablename__ = "niche_metrics"


class DemandTrend(JsonTenantRecord):
    __tablename__ = "demand_trend"


class ProductIdea(JsonTenantRecord):
    __tablename__ = "product_ideas"


class Supplier(Base, TenantBound):
    __tablename__ = "suppliers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(String(300))
    marketplace: Mapped[str] = mapped_column(String(120), default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PvzPointRecord(Base, TenantBound):
    __tablename__ = "pvz_points"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(String(300))
    monthly_turnover: Mapped[float] = mapped_column(Float, default=0)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PvzEmployeeRecord(Base, TenantBound):
    __tablename__ = "pvz_employees"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    point_id: Mapped[str] = mapped_column(ForeignKey("pvz_points.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    hourly_rate: Mapped[float] = mapped_column(Float, default=0)
    preferred_days: Mapped[list] = mapped_column(JSON, default=list)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PvzShift(JsonTenantRecord):
    __tablename__ = "pvz_shifts"


class PvzPayroll(JsonTenantRecord):
    __tablename__ = "pvz_payroll"


class PvzFine(JsonTenantRecord):
    __tablename__ = "pvz_fines"


class CardAsset(JsonTenantRecord):
    __tablename__ = "card_assets"


class CardVariant(JsonTenantRecord):
    __tablename__ = "card_variants"


class ContentBlock(JsonTenantRecord):
    __tablename__ = "content_blocks"


class RiskSignal(JsonTenantRecord):
    __tablename__ = "risk_signals"


class ClickFraud(JsonTenantRecord):
    __tablename__ = "click_fraud"


class WhitehatTip(JsonTenantRecord):
    __tablename__ = "whitehat_tips"


class RuleChange(JsonTenantRecord):
    __tablename__ = "rule_changes"


class RuleVersion(JsonTenantRecord):
    __tablename__ = "rule_versions"


class CashOperation(JsonTenantRecord):
    __tablename__ = "cash_ops"


class ReceiptRecord(JsonTenantRecord):
    __tablename__ = "receipts"


class StudioSpec(JsonTenantRecord):
    __tablename__ = "studio_specs"


class StudioBuild(JsonTenantRecord):
    __tablename__ = "studio_builds"


class IncidentRecord(JsonTenantRecord):
    __tablename__ = "incidents"


class AlertRecord(JsonTenantRecord):
    __tablename__ = "alerts"


class EvalRun(JsonTenantRecord):
    __tablename__ = "eval_runs"


class SourceChange(JsonTenantRecord):
    __tablename__ = "source_changes"


class KnowledgeProposal(JsonTenantRecord):
    __tablename__ = "knowledge_proposals"


class PluginManifest(Base, TenantBound):
    __tablename__ = "plugin_manifests"
    __table_args__ = (
        UniqueConstraint("tenant_id", "plugin_id", name="uq_plugin_manifest_tenant_plugin"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    plugin_id: Mapped[str] = mapped_column(String(120), index=True)
    label: Mapped[str] = mapped_column(String(160))
    surface: Mapped[str] = mapped_column(String(32), default="bot")
    module_id: Mapped[str] = mapped_column(String(32), index=True)
    action: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    requires_confirm: Mapped[int] = mapped_column(Integer, default=1)
    schema: Mapped[dict] = mapped_column(JSON, default=dict)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SelfUpdateRun(Base, TenantBound):
    __tablename__ = "self_update_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    source: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(32), default="planned", index=True)
    current_snapshot: Mapped[str] = mapped_column(String(160), default="")
    candidate_snapshot: Mapped[str] = mapped_column(String(160), default="")
    gates: Mapped[dict] = mapped_column(JSON, default=dict)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HealthCheck(Base, TenantBound):
    __tablename__ = "health_checks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    component: Mapped[str] = mapped_column(String(120), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SemanticMemory(Base, TenantBound):
    __tablename__ = "semantic_memory"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    scope: Mapped[str] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(300), default="")
    text: Mapped[str] = mapped_column(Text)
    text_hash: Mapped[str] = mapped_column(String(64), index=True)
    embedding_model: Mapped[str] = mapped_column(String(120), default="bge-m3-local")
    vector: Mapped[list] = mapped_column(VECTOR(1024), default=list)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
