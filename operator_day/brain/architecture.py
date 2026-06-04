from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from operator_day.brain.llm import LlmRouter
from operator_day.connectors.catalog import operation_catalog
from operator_day.models import Base
from operator_day.modules.implementations import ModuleRegistry


@dataclass(frozen=True)
class ArchitectureReview:
    text: str
    model: str
    used_fallback: bool
    tokens_estimate: int


@dataclass(frozen=True)
class ArchitectureGate:
    topology: dict[str, Any]
    verdict: str
    text: str
    blockers: tuple[str, ...]
    model: str
    used_fallback: bool
    tokens_estimate: int


class ArchitectureReviewService:
    def __init__(self, llm: LlmRouter) -> None:
        self.llm = llm

    def build_topology(self) -> dict[str, Any]:
        operations = operation_catalog()
        modules = ModuleRegistry.default().modules
        tables = sorted(Base.metadata.tables)
        return {
            "product": "operator_day",
            "mode": "bot_plus_miniapp_autonomous_backend",
            "llm_role": "local_primary_external_architect_opus_4_8_when_enabled",
            "external_accounts": {
                "ozon": {
                    "auth": "Client-Id + Api-Key",
                    "safe_probe": "ProductAPI_GetProductList",
                    "live_sync": "catalog/read, validation/read, writes only after OK",
                },
                "wb": {
                    "auth": "Bearer seller token",
                    "safe_probe": "WB_Content_GetCardsList",
                    "live_sync": "catalog/read, validation/read, writes only after OK",
                },
                "yandex_market": {
                    "auth": "Bearer partner token + campaignId",
                    "safe_probe": "YM_GetOfferPrices",
                    "live_sync": "catalog/read, validation/read, writes only after OK",
                },
                "pvz": {
                    "auth": "tenant role context",
                    "safe_probe": "manual point/staff import",
                    "live_sync": "schedule/payroll from tenant DB",
                },
            },
            "server_layers": [
                "FastAPI headers or Telegram init data -> TenantContext",
                "RBAC policy checks",
                "connector catalog",
                "transport safety gates",
                "repositories with tenant scope",
                "orchestrator scoring",
                "Telegram bot buttons",
                "Telegram Mini App / PWA shell",
                "plugin manifest registry",
                "self-update sandbox and last-known-good snapshots",
            ],
            "api_contracts": [
                "/api/accounts",
                "/api/accounts/{account_id}/validate",
                "/api/accounts/{account_id}/sync/catalog",
                "/api/catalog/import",
                "/api/reviews/import",
                "/api/claims/import",
                "/api/pvz/import",
                "/api/tasks/morning",
                "/api/tasks/{task_id}/confirm",
                "/api/plugins",
                "/api/self-update/plan",
                "/api/self-update/run",
                "/api/brain/architecture-gate",
                "/api/brain/llm-status",
                "/metrics",
                "/telegram/webhook",
            ],
            "workers": [
                "operator_day.collect_morning",
                "operator_day.sync_catalog",
                "operator_day.sync_ozon_catalog",
                "operator_day.self_update_gate",
            ],
            "modules": [module.module_id.value for module in modules],
            "connector_operations": {
                key: {
                    "platform": operation.platform,
                    "method": operation.method,
                    "safety": operation.safety.value,
                    "endpoint": operation.endpoint,
                    "rate_limit_key": operation.rate_limit_key,
                }
                for key, operation in sorted(operations.items())
            },
            "database_tables": tables,
            "safety_invariants": [
                "no marketplace write without explicit OK and idempotency",
                "tokens encrypted at rest and never returned in API responses",
                "tenant_id on every business table with Postgres RLS or repository filters",
                "claim deadlines are source-linked, not hardcoded as truth",
                "each action payload carries 30+ skills/plugins and 10 mcp_checks",
                (
                    "local LLM is the primary brain; Opus 4.8 via FreeModel is the "
                    "optional senior architecture reviewer"
                ),
                "prompt-injection text is treated as data before LLM review",
                "PVZ operators cannot change staff rates",
                "plugins are manifests, not arbitrary user code",
                "self-update never promotes without sandbox/test/canary gates",
            ],
            "readiness_gates": [
                "real_marketplace_tokens",
                "marketplace_api_verification",
                "claim_deadline_policies",
                "prod_llm_gate",
                "tests_and_smoke",
                "secret_scan",
                "miniapp_build",
            ],
        }

    async def build_review(self) -> ArchitectureReview:
        modules = ", ".join(module.module_id.value for module in ModuleRegistry.default().modules)
        operations = ", ".join(sorted(operation_catalog().keys())[:20])
        prompt = (
            "Проверь дерево продукта «Оператор дня» для пилота селлеров и ПВЗ. "
            "Кратко опиши поток: ЛК/API площадок -> transport/safety -> workers -> БД -> "
            "orchestrator -> Telegram bot/Mini App -> действие -> аудит. "
            f"Модули: {modules}. Операции коннекторов: {operations}. "
            "Не выдумывай неподтверждённые endpoint. Отметь только практичные блокеры."
        )
        response = await self.llm.complete_json_safe(prompt, max_tokens=700)
        text = response.text
        if response.used_fallback:
            text = (
                "ЛК площадок дают данные через проверенные операции connector catalog. "
                "Transport проверяет safety, лимиты и retry, затем workers сохраняют снимки в БД. "
                "БД хранит tenant_id, задачи, аудит, usage LLM и кабинеты без раскрытия секретов. "
                "Orchestrator ранжирует дела по деньгам, срочности, риску и уверенности. "
                "Бот и Mini App показывают простые кнопки; "
                "опасные действия выполняются только после ОК. "
                "Self-update остаётся на last known good, пока sandbox, тесты и canary не зелёные."
            )
        return ArchitectureReview(
            text=text,
            model=response.model,
            used_fallback=response.used_fallback,
            tokens_estimate=response.tokens_estimate,
        )

    async def build_gate(
        self,
        *,
        force_offline: bool = False,
        disabled_reason: str = (
            "prod LLM gate не выполнен: локальная модель недоступна или smoke-флаг выключен"
        ),
    ) -> ArchitectureGate:
        topology = self.build_topology()
        prompt = (
            "Ты проверяешь автономность и безопасность продукта. "
            "Найди только практические блокеры: ЛК/API-БД, права, секреты, self-update, "
            "плагины, Mini App, write без OK. "
            "Ответь коротко: verdict=pass|needs_work, blockers=[], fixes=[]. "
            f"TOPOLOGY_JSON={json.dumps(topology, ensure_ascii=False, sort_keys=True)}"
        )
        if force_offline:
            return ArchitectureGate(
                topology=topology,
                verdict="needs_work",
                text=(
                    "Топология собрана, но prod LLM gate не запускался. "
                    "Для live-пилота нужна доступная локальная модель "
                    "или явно включённый smoke-прогон."
                ),
                blockers=(disabled_reason,),
                model="prod-gate-disabled",
                used_fallback=True,
                tokens_estimate=max(1, int(len(prompt.split()) * 1.35)),
            )
        response = await self.llm.complete_json_safe(prompt, max_tokens=900)
        blockers = _extract_blockers(response.text)
        verdict = "needs_work" if blockers else "pass"
        if response.used_fallback:
            blockers = (
                "prod LLM gate не выполнен чисто: "
                f"использована деградация или замена модели ({response.model})",
            )
            verdict = "needs_work"
        return ArchitectureGate(
            topology=topology,
            verdict=verdict,
            text=response.text,
            blockers=blockers,
            model=response.model,
            used_fallback=response.used_fallback,
            tokens_estimate=response.tokens_estimate,
        )


def _extract_blockers(text: str) -> tuple[str, ...]:
    lowered = text.lower()
    if "blockers=[]" in lowered or '"blockers": []' in lowered or "блокеры: нет" in lowered:
        return ()
    markers = ("blocker", "блокер", "needs_work", "нужно исправить")
    if any(marker in lowered for marker in markers):
        return ("prod_llm_gate_reported_blockers",)
    return ()
