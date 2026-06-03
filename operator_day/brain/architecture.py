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
            "mode": "backend_only_no_frontend_no_mini_app",
            "llm_role": "opus_4_8_senior_architect_gate",
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
                "FastAPI headers -> TenantContext",
                "policy checks",
                "connector catalog",
                "transport safety gates",
                "repositories with tenant scope",
                "orchestrator ranking",
                "Telegram button handlers",
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
                "/api/brain/architecture-gate",
                "/api/brain/llm-status",
                "/telegram/webhook",
            ],
            "workers": [
                "operator_day.collect_morning",
                "operator_day.sync_catalog",
                "operator_day.sync_ozon_catalog",
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
                "tenant_id on every business table with Postgres RLS",
                "claim deadlines are source-linked, not hardcoded as truth",
                "each action payload carries 30+ skills/plugins and 10 mcp_checks",
                "Opus 4.8 calls are budget-gated and read FREEMODEL_API_KEY only from env",
                "PVZ operators cannot change staff rates",
                "frontend and mini app are intentionally out of current scope",
            ],
            "readiness_gates": [
                "real_marketplace_tokens",
                "marketplace_api_verification",
                "claim_deadline_policies",
                "llm_architecture_gate",
                "tests_and_smoke",
                "secret_scan",
            ],
        }

    async def build_review(self) -> ArchitectureReview:
        modules = ", ".join(module.module_id.value for module in ModuleRegistry.default().modules)
        operations = ", ".join(sorted(operation_catalog().keys())[:20])
        prompt = (
            "Проверь дерево backend-проекта «Оператор дня» для пилота селлеров и ПВЗ. "
            "Опиши коротко: ЛК/API площадок -> transport/safety -> workers -> БД -> "
            "orchestrator -> Telegram-кнопки. "
            f"Модули: {modules}. "
            f"Операции коннекторов: {operations}. "
            "Не выдумывай неподтвержденные endpoint и отметь, где нужна API verification."
        )
        response = await self.llm.complete_json_safe(prompt, max_tokens=700)
        text = response.text
        if response.used_fallback:
            text = (
                "ЛК площадок дают данные через проверенные операции connector catalog. "
                "Transport сначала проверяет safety и лимиты, потом workers сохраняют снимки в БД. "
                "БД хранит tenant_id, задачи, аудит, usage LLM и кабинеты без секретов. "
                "Orchestrator собирает 23 направления в утренний список. "
                "Telegram показывает только простые кнопки и не делает опасные действия без ОК."
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
            "live Opus 4.8 gate не выполнен: "
            "FREEMODEL_API_KEY/LLM_SMOKE_ENABLED не активны"
        ),
    ) -> ArchitectureGate:
        topology = self.build_topology()
        prompt = (
            "Ты Opus 4.8 в роли senior+ архитектора и конструктора backend-продукта. "
            "Проверь дерево проекта для пилота реальных селлеров и владельцев ПВЗ. "
            "Найди только практические блокеры автономной работы, конфликтующие связи ЛК/API-БД, "
            "ошибки безопасности, пробелы readiness и места, где нельзя делать write без OK. "
            "Ответь коротко на русском: verdict=pass|needs_work, blockers=[], fixes=[]. "
            "Не выдумывай endpoint и не предлагай фронт/Mini App. "
            f"TOPOLOGY_JSON={json.dumps(topology, ensure_ascii=False, sort_keys=True)}"
        )
        if force_offline:
            return ArchitectureGate(
                topology=topology,
                verdict="needs_work",
                text=(
                    "Топология проекта собрана, но live Opus 4.8 gate не запускался. "
                    "Для сдачи live-пилота нужен явный прогон через env-key "
                    "и включенный smoke-флаг."
                ),
                blockers=(disabled_reason,),
                model="live-gate-disabled",
                used_fallback=True,
                tokens_estimate=max(1, int(len(prompt.split()) * 1.35)),
            )
        response = await self.llm.complete_json_safe(prompt, max_tokens=900)
        blockers = _extract_blockers(response.text)
        verdict = "needs_work" if blockers else "pass"
        if response.used_fallback:
            if response.model in {"offline-template", "budget-fallback", "provider-route-fallback"}:
                blocker = (
                    "live Opus 4.8 gate не выполнен: "
                    "FREEMODEL_API_KEY/LLM_SMOKE_ENABLED не активны или provider route недоступен"
                )
            else:
                blocker = (
                    "live Opus 4.8 gate не выполнен: "
                    f"FreeModel вернул {response.model} вместо claude-opus-4-8"
                )
            blockers = (blocker,)
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
        return ("llm_architecture_gate_reported_blockers",)
    return ()
