from __future__ import annotations

from operator_day.domain import ModuleId

CORE_MCP_CHECKS = (
    "tenant_scope",
    "role_policy",
    "source_freshness",
    "api_capability",
    "rate_limit_window",
    "idempotency_key",
    "money_effect",
    "deadline_window",
    "confidence_score",
    "audit_event",
)

CORE_PLUGIN = "operator_day_core"

PLUGIN_CONTRACTS = {
    "wb_seller_api": (ModuleId.ACCOUNTS, ModuleId.SUPPLIES, ModuleId.FINANCE),
    "wb_promotion_api": (ModuleId.ADS,),
    "ozon_seller_api": (ModuleId.ACCOUNTS, ModuleId.FINANCE, ModuleId.FORECAST),
    "ozon_performance_api": (ModuleId.ADS,),
    "yandex_market_partner_api": (ModuleId.ACCOUNTS, ModuleId.FINANCE),
    "telegram_bot_api": (ModuleId.MORNING, ModuleId.REVIEWS),
    "external_llm_accelerator": (ModuleId.REVIEWS, ModuleId.SUPERVISOR),
    "pvz_shift_engine": (ModuleId.PVZ, ModuleId.ACCOUNTING),
}

SKILL_CONTRACTS = {
    "account_token_guard": (ModuleId.ACCOUNTS,),
    "catalog_snapshot_sync": (ModuleId.ACCOUNTS,),
    "unit_margin_guard": (ModuleId.UNIT,),
    "commission_delta_watch": (ModuleId.UNIT, ModuleId.RULES),
    "reverse_keyword_research": (ModuleId.SEO,),
    "listing_score_0_100": (ModuleId.SEO, ModuleId.CONTENT),
    "keyword_position_history": (ModuleId.SEO, ModuleId.COMPETITORS),
    "supply_draft_builder": (ModuleId.SUPPLIES,),
    "barcode_packaging_check": (ModuleId.SUPPLIES,),
    "review_positive_reply": (ModuleId.REVIEWS,),
    "review_negative_escalation": (ModuleId.REVIEWS,),
    "question_answer_draft": (ModuleId.REVIEWS,),
    "competitor_price_watch": (ModuleId.COMPETITORS,),
    "card_hijack_watch": (ModuleId.COMPETITORS,),
    "warehouse_priority_watch": (ModuleId.COMPETITORS, ModuleId.FORECAST),
    "floor_price_repricer": (ModuleId.REPRICER,),
    "game_theory_repricer": (ModuleId.REPRICER,),
    "fifo_cogs": (ModuleId.FINANCE,),
    "weekly_report_reconciliation": (ModuleId.FINANCE, ModuleId.CLAIMS),
    "return_fraud_watch": (ModuleId.ANTIFRAUD,),
    "pvz_substitution_guard": (ModuleId.ANTIFRAUD, ModuleId.PVZ),
    "demand_forecast": (ModuleId.FORECAST,),
    "warehouse_distribution": (ModuleId.FORECAST,),
    "pvz_2_2_schedule": (ModuleId.PVZ,),
    "pvz_payroll": (ModuleId.PVZ, ModuleId.ACCOUNTING),
    "marketplace_rules_radar": (ModuleId.RULES, ModuleId.RADAR),
    "accounting_export": (ModuleId.ACCOUNTING,),
    "billing_usage_meter": (ModuleId.BILLING,),
    "llm_budget_supervisor": (ModuleId.SUPERVISOR,),
    "secret_redaction_guard": (ModuleId.SUPERVISOR,),
    "feedback_learning_loop": (ModuleId.LEARNING,),
    "github_habr_radar": (ModuleId.RADAR,),
    "ads_drr_bidder": (ModuleId.ADS,),
    "ads_dayparting": (ModuleId.ADS,),
    "ads_negative_keywords": (ModuleId.ADS,),
    "claim_evidence_builder": (ModuleId.CLAIMS,),
    "claim_deadline_guard": (ModuleId.CLAIMS,),
    "niche_opportunity_score": (ModuleId.NICHES,),
    "supplier_shortlist": (ModuleId.NICHES,),
    "external_content_brief": (ModuleId.CONTENT,),
    "infographic_variant_brief": (ModuleId.CONTENT,),
    "click_fraud_guard": (ModuleId.ACCOUNT_GUARD,),
    "account_takeover_watch": (ModuleId.ACCOUNT_GUARD,),
}


def skills_for_module(module_id: ModuleId) -> list[str]:
    relevant = [
        name
        for name, module_ids in SKILL_CONTRACTS.items()
        if module_id in module_ids
    ]
    rest = [name for name in SKILL_CONTRACTS if name not in relevant]
    return [*relevant, *rest]


def plugins_for_module(module_id: ModuleId) -> list[str]:
    relevant = [
        name
        for name, module_ids in PLUGIN_CONTRACTS.items()
        if module_id in module_ids
    ]
    rest = [name for name in PLUGIN_CONTRACTS if name not in relevant]
    return [CORE_PLUGIN, *relevant, *rest]


def enrich_action_payload(module_id: ModuleId, payload: dict) -> dict:
    payload.setdefault("skills", skills_for_module(module_id))
    payload.setdefault("plugins", plugins_for_module(module_id))
    payload.setdefault("mcp_checks", list(CORE_MCP_CHECKS))
    payload.setdefault(
        "answer_basis",
        [
            "данные кабинета или replay-снимок",
            "расчет денег, срочности и уверенности",
            "права пользователя и журнал действия",
        ],
    )
    return payload


def all_operator_capabilities() -> list[dict[str, str]]:
    skills = [{"kind": "skill", "name": name} for name in SKILL_CONTRACTS]
    plugins = [{"kind": "plugin", "name": CORE_PLUGIN}]
    plugins.extend({"kind": "plugin", "name": name} for name in PLUGIN_CONTRACTS)
    return skills + plugins
