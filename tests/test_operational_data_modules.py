from httpx import ASGITransport, AsyncClient

from operator_day.domain import ModuleId
from operator_day.main import create_app

HEADERS = {"X-Tenant-Id": "ops-tail", "X-User-Id": "owner", "X-Role": "owner"}


async def test_operational_data_feeds_tail_modules_and_confirm_flow() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        for kind, records in {
            "rule_changes": [
                {
                    "id": "rule-2026-storage",
                    "title": "WB поменял тариф хранения",
                    "source": "official-wb-rules",
                    "source_url": "https://seller.wildberries.ru/help-center",
                    "affected_revenue": 12345,
                    "impact": "margin",
                }
            ],
            "cash_ops": [
                {
                    "id": "cash-june-1",
                    "title": "Касса ПВЗ не сошлась с выплатой",
                    "source": "manual-cash-upload",
                    "amount": 142300,
                    "unmatched_amount": 3200,
                }
            ],
            "studio_specs": [
                {
                    "id": "studio-button-1",
                    "title": "Добавить кнопку сверки еженедельного отчета",
                    "module_id": "M08_FINANCE",
                    "source": "seller-request",
                }
            ],
            "incidents": [
                {
                    "id": "incident-token-budget",
                    "title": "Лимит модели близко к порогу",
                    "severity": "high",
                    "status": "open",
                    "source": "llm-budget-guard",
                }
            ],
            "eval_runs": [
                {
                    "id": "eval-review-answers",
                    "title": "Ответы на отзывы стали сухими",
                    "score": 0.66,
                    "prompt_version": "reviews-v3",
                    "source": "feedback-loop",
                }
            ],
            "source_changes": [
                {
                    "id": "source-restate",
                    "title": "Restate обновил durable workflow",
                    "source": "github-radar",
                    "source_url": "https://github.com/restatedev/restate",
                }
            ],
        }.items():
            imported = await client.post(
                "/api/operational-data/import",
                headers=HEADERS,
                json={"kind": kind, "records": records},
            )
            assert imported.status_code == 200
            assert imported.json()["count"] == 1

        tasks_response = await client.get("/api/tasks/morning?limit=50", headers=HEADERS)
        tasks = tasks_response.json()
        by_module = {task["moduleId"]: task for task in tasks}

        rules = by_module[ModuleId.RULES.value]
        accounting = by_module[ModuleId.ACCOUNTING.value]
        billing = by_module[ModuleId.BILLING.value]
        supervisor = by_module[ModuleId.SUPERVISOR.value]
        learning = by_module[ModuleId.LEARNING.value]
        radar = by_module[ModuleId.RADAR.value]

        assert "WB поменял тариф хранения" in rules["shortText"]
        assert rules["moneyEffect"] == 12345
        assert rules["payload"]["source_url"].startswith("https://seller.wildberries.ru")
        assert accounting["payload"]["cash_operation_id"]
        assert accounting["moneyEffect"] == 3200
        assert billing["payload"]["target_module"] == "M08_FINANCE"
        assert supervisor["risk"] == "human"
        assert supervisor["payload"]["severity"] == "high"
        assert learning["risk"] == "confirm"
        assert learning["payload"]["eval_score"] == 0.66
        assert radar["payload"]["source_url"] == "https://github.com/restatedev/restate"

        confirmed = await client.post(
            f"/api/tasks/{rules['taskId']}/confirm",
            headers={**HEADERS, "X-Idempotency-Key": "rule-confirm"},
        )
        stored = await client.get("/api/operational-data/rule_versions", headers=HEADERS)

    assert confirmed.status_code == 200
    assert confirmed.json()["auditEvent"]["action"] == "rule_recalculation_recorded"
    assert confirmed.json()["auditEvent"]["marketplace_write"] == "not_attempted"
    assert stored.status_code == 200
    assert stored.json()["records"][0]["payload"]["rule_change_id"] == "rule-2026-storage"
