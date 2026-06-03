import json

import httpx

from operator_day.brain.llm import LlmRouter
from operator_day.config import Settings


async def test_llm_router_falls_back_when_budget_would_be_exceeded() -> None:
    settings = Settings(
        freemodel_api_key="test-secret",
        llm_daily_token_budget=3,
        freemodel_model="claude-opus-4-8",
    )
    router = LlmRouter(settings)

    response = await router.complete_json_safe("ответ на отзыв покупателю", max_tokens=50)

    assert response.used_fallback is True
    assert response.model == "budget-fallback"
    assert "Спасибо" in response.text


async def test_llm_router_uses_responses_api_and_detects_model_substitution() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "model": "gpt-5.4",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "verdict=pass"}],
                    }
                ],
                "usage": {"total_tokens": 12},
            },
        )

    transport = httpx.MockTransport(handler)

    def client_factory(**kwargs) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=transport, **kwargs)

    settings = Settings(
        freemodel_api_key="test-secret",
        freemodel_model="claude-opus-4-8",
        freemodel_base_url="https://api.freemodel.dev/v1",
    )
    router = LlmRouter(settings, client_factory=client_factory)

    response = await router.complete_json_safe("проверь архитектуру", max_tokens=20)

    assert response.used_fallback is True
    assert response.model == "gpt-5.4"
    assert str(requests[0].url) == "https://api.freemodel.dev/v1/responses"
    assert requests[0].headers["authorization"] == "Bearer test-secret"
    body = json.loads(requests[0].content)
    assert body["instructions"]
    assert body["input"] == "проверь архитектуру"


async def test_task_result_records_llm_token_usage(session_factory) -> None:
    from sqlalchemy import select

    from operator_day.brain.orchestrator import MorningOrchestrator
    from operator_day.domain import ModuleId, Role, TenantContext
    from operator_day.models import TokenUsage
    from operator_day.repositories import TaskRepository

    ctx = TenantContext(tenant_id="seller-llm", user_id="owner-llm", role=Role.OWNER)
    orchestrator = MorningOrchestrator()
    async with session_factory() as session:
        repo = TaskRepository(session)
        tasks = await orchestrator.collect_all(ctx)
        task = next(
            item
            for item in tasks
            if item.module_id == ModuleId.REVIEWS and item.payload.get("rating") == 5
        )
        result = await orchestrator.execute_prepared(ctx, task)
        await repo.save_result(ctx, task, result, idempotency_key="llm-tokens")

        rows = (await session.execute(select(TokenUsage))).scalars().all()

    assert rows
    assert rows[0].payload["tokens"] > 0
    assert rows[0].payload["model"] == "offline-template"
