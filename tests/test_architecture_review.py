from httpx import ASGITransport, AsyncClient

from operator_day.brain.architecture import ArchitectureReviewService
from operator_day.brain.llm import LlmResponse, LlmRouter
from operator_day.config import Settings, get_settings
from operator_day.main import create_app


async def test_architecture_review_uses_llm_router_fallback_without_key() -> None:
    service = ArchitectureReviewService(LlmRouter(Settings(freemodel_api_key="")))

    review = await service.build_review()

    assert review.model == "offline-template"
    assert review.used_fallback is True
    assert "БД" in review.text
    assert "ЛК" in review.text
    assert review.tokens_estimate > 0


async def test_architecture_gate_builds_machine_readable_topology_with_fallback() -> None:
    service = ArchitectureReviewService(LlmRouter(Settings(freemodel_api_key="")))

    gate = await service.build_gate()

    assert gate.verdict == "needs_work"
    assert gate.used_fallback is True
    assert "external_accounts" in gate.topology
    assert "connector_operations" in gate.topology
    assert "database_tables" in gate.topology
    assert "/api/accounts/{account_id}/validate" in gate.topology["api_contracts"]
    assert "prod LLM gate" in gate.blockers[0]


async def test_architecture_gate_accepts_clean_prod_llm_verdict() -> None:
    class FakeProdLlm:
        async def complete_json_safe(self, prompt: str, *, max_tokens: int = 500):
            assert "TOPOLOGY_JSON=" in prompt
            assert "ProductAPI_GetProductList" in prompt
            return LlmResponse(
                text='verdict=pass, blockers=[], fixes=["keep current gates"]',
                model="qwen3:8b",
                used_fallback=False,
                tokens_estimate=111,
            )

    gate = await ArchitectureReviewService(FakeProdLlm()).build_gate()  # type: ignore[arg-type]

    assert gate.verdict == "pass"
    assert gate.model == "qwen3:8b"
    assert gate.blockers == ()


async def test_architecture_gate_reports_provider_model_substitution() -> None:
    class FakeSubstitutedModel:
        async def complete_json_safe(self, prompt: str, *, max_tokens: int = 500):
            return LlmResponse(
                text='verdict=needs_work, blockers=["api check"]',
                model="gpt-5.4",
                used_fallback=True,
                tokens_estimate=222,
            )

    gate = await ArchitectureReviewService(FakeSubstitutedModel()).build_gate()  # type: ignore[arg-type]

    assert gate.verdict == "needs_work"
    assert gate.model == "gpt-5.4"
    assert "замена модели" in gate.blockers[0]


async def test_architecture_review_api_is_owner_only() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        denied = await client.get(
            "/api/brain/architecture-review",
            headers={"X-Tenant-Id": "arch", "X-User-Id": "pvz", "X-Role": "pvz_operator"},
        )
        ok = await client.get(
            "/api/brain/architecture-review",
            headers={"X-Tenant-Id": "arch", "X-User-Id": "owner", "X-Role": "owner"},
        )
        gate = await client.get(
            "/api/brain/architecture-gate",
            headers={"X-Tenant-Id": "arch", "X-User-Id": "owner", "X-Role": "owner"},
        )

    assert denied.status_code == 403
    assert ok.status_code == 200
    assert ok.json()["usedFallback"] is True
    assert gate.status_code == 200
    assert gate.json()["topology"]["llm_role"] == "model_agnostic_prod_gate_local_primary"
    assert gate.json()["model"] == "prod-gate-disabled"


async def test_architecture_gate_does_not_spend_tokens_without_smoke_flag(monkeypatch) -> None:
    monkeypatch.setenv("FREEMODEL_API_KEY", "fe_oa_example")
    monkeypatch.delenv("LLM_SMOKE_ENABLED", raising=False)
    get_settings.cache_clear()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=create_app()), base_url="http://test"
        ) as client:
            gate = await client.get(
                "/api/brain/architecture-gate?live=true",
                headers={"X-Tenant-Id": "arch-safe", "X-User-Id": "owner", "X-Role": "owner"},
            )
    finally:
        get_settings.cache_clear()

    body = gate.json()
    assert gate.status_code == 200
    assert body["verdict"] == "needs_work"
    assert body["usedFallback"] is True
    assert body["model"] == "prod-gate-disabled"
    assert "smoke-флаг" in body["blockers"][0]


async def test_llm_status_is_owner_only_and_does_not_run_live_without_key(monkeypatch) -> None:
    monkeypatch.delenv("FREEMODEL_API_KEY", raising=False)
    monkeypatch.delenv("LLM_SMOKE_ENABLED", raising=False)
    get_settings.cache_clear()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=create_app()), base_url="http://test"
        ) as client:
            denied = await client.get(
                "/api/brain/llm-status",
                headers={"X-Tenant-Id": "llm", "X-User-Id": "pvz", "X-Role": "pvz_operator"},
            )
            ok = await client.get(
                "/api/brain/llm-status?live=true",
                headers={"X-Tenant-Id": "llm", "X-User-Id": "owner", "X-Role": "owner"},
            )
    finally:
        get_settings.cache_clear()

    assert denied.status_code == 403
    body = ok.json()
    assert body["configured"] is True
    assert body["model"] == "qwen3:8b"
    assert body["primaryProvider"] == "local"
    assert body["primaryModel"] == "qwen3:8b"
    assert body["externalEnabled"] is False
    assert body["liveCheckRequested"] is True
    assert body["liveCheckRan"] is False
    assert body["status"] == "live_disabled"
