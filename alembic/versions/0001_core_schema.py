from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0001_core_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("plan", sa.String(64), nullable=False, server_default="pilot"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("tg_id", sa.String(64), nullable=False, index=True),
        sa.Column("role", sa.String(64), nullable=False),
        sa.Column("name", sa.String(200), nullable=False, server_default=""),
    )
    op.create_table(
        "accounts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("platform", sa.String(32), nullable=False, index=True),
        sa.Column("title", sa.String(200), nullable=False, server_default=""),
        sa.Column("token_enc", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="new"),
        sa.Column("token_fingerprint", sa.String(32), nullable=False, server_default=""),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_table(
        "products",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("account_id", sa.String(64), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("sku", sa.String(120), nullable=False, index=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("category", sa.String(200), nullable=False, server_default=""),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("cost", sa.Float(), nullable=False, server_default="0"),
    )
    op.create_table(
        "stocks",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column(
            "product_id",
            sa.String(64),
            sa.ForeignKey("products.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("warehouse", sa.String(200), nullable=False, server_default=""),
        sa.Column("quantity", sa.Integer(), nullable=False),
    )
    op.create_table(
        "reviews",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("product_id", sa.String(64), nullable=False, index=True),
        sa.Column("source", sa.String(32), nullable=False, server_default="ozon", index=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("answer_status", sa.String(32), nullable=False, server_default="new"),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("module_id", sa.String(32), nullable=False, index=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("short_text", sa.Text(), nullable=False),
        sa.Column("action_label", sa.String(160), nullable=False),
        sa.Column("risk", sa.String(32), nullable=False, index=True),
        sa.Column("status", sa.String(32), nullable=False, index=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("money_effect", sa.Float(), nullable=False, server_default="0"),
        sa.Column("urgency", sa.Float(), nullable=False, server_default="0.1"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "feedback",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("task_id", sa.String(64), nullable=False, index=True),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False, server_default=""),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("user_id", sa.String(64), nullable=False, index=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("before_after", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "action_executions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("task_id", sa.String(64), nullable=False, index=True),
        sa.Column("idempotency_key", sa.String(160), nullable=False, index=True),
        sa.Column("status", sa.String(32), nullable=False, index=True),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "tenant_id",
            "task_id",
            "idempotency_key",
            name="uq_action_idempotency",
        ),
    )
    for table in (
        "seo_queries",
        "seo_drafts",
        "keyword_positions",
        "keyword_freq",
        "competitor_keywords",
        "review_aspects",
        "cogs_batches",
        "warehouse_distribution",
        "token_usage",
        "ad_campaigns",
        "ad_keywords",
        "bid_rules",
        "bid_history",
        "competitor_bids",
        "keyword_clusters",
        "claims",
        "claim_items",
        "lost_damaged",
        "reconciliations",
    ):
        op.create_table(
            table,
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
            sa.Column("product_id", sa.String(64), nullable=False, server_default="", index=True),
            sa.Column("source", sa.String(120), nullable=False, server_default=""),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
    op.create_table(
        "claim_deadline_policies",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("platform", sa.String(32), nullable=False, index=True),
        sa.Column("claim_type", sa.String(120), nullable=False, index=True),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=False),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for table in (
        "niches",
        "niche_metrics",
        "demand_trend",
        "product_ideas",
        "pvz_shifts",
        "pvz_payroll",
        "pvz_fines",
        "card_assets",
        "card_variants",
        "content_blocks",
        "risk_signals",
        "click_fraud",
        "whitehat_tips",
    ):
        op.create_table(
            table,
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
            sa.Column("product_id", sa.String(64), nullable=False, server_default="", index=True),
            sa.Column("source", sa.String(120), nullable=False, server_default=""),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
    op.create_table(
        "suppliers",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("marketplace", sa.String(120), nullable=False, server_default=""),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "pvz_points",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("monthly_turnover", sa.Float(), nullable=False, server_default="0"),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "pvz_employees",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column(
            "point_id",
            sa.String(64),
            sa.ForeignKey("pvz_points.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("hourly_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("preferred_days", sa.JSON(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for table in (
        "users",
        "accounts",
        "products",
        "stocks",
        "reviews",
        "tasks",
        "feedback",
        "audit_log",
        "action_executions",
        "seo_queries",
        "seo_drafts",
        "keyword_positions",
        "keyword_freq",
        "competitor_keywords",
        "review_aspects",
        "cogs_batches",
        "warehouse_distribution",
        "token_usage",
        "ad_campaigns",
        "ad_keywords",
        "bid_rules",
        "bid_history",
        "competitor_bids",
        "keyword_clusters",
        "claims",
        "claim_items",
        "lost_damaged",
        "reconciliations",
        "claim_deadline_policies",
        "niches",
        "niche_metrics",
        "demand_trend",
        "product_ideas",
        "suppliers",
        "pvz_points",
        "pvz_employees",
        "pvz_shifts",
        "pvz_payroll",
        "pvz_fines",
        "card_assets",
        "card_variants",
        "content_blocks",
        "risk_signals",
        "click_fraud",
        "whitehat_tips",
    ):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_{table}
            ON {table}
            USING (tenant_id = current_setting('app.tenant_id', true))
            """
        )


def downgrade() -> None:
    for table in (
        "whitehat_tips",
        "click_fraud",
        "risk_signals",
        "content_blocks",
        "card_variants",
        "card_assets",
        "pvz_fines",
        "pvz_payroll",
        "pvz_shifts",
        "pvz_employees",
        "pvz_points",
        "suppliers",
        "product_ideas",
        "demand_trend",
        "niche_metrics",
        "niches",
        "reconciliations",
        "lost_damaged",
        "claim_items",
        "claims",
        "claim_deadline_policies",
        "keyword_clusters",
        "competitor_bids",
        "bid_history",
        "bid_rules",
        "ad_keywords",
        "ad_campaigns",
        "token_usage",
        "warehouse_distribution",
        "cogs_batches",
        "review_aspects",
        "competitor_keywords",
        "keyword_freq",
        "keyword_positions",
        "seo_drafts",
        "seo_queries",
        "feedback",
        "action_executions",
        "audit_log",
        "tasks",
        "reviews",
        "stocks",
        "products",
        "accounts",
        "users",
        "tenants",
    ):
        op.drop_table(table)
