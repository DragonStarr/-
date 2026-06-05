from pathlib import Path

from httpx import ASGITransport, AsyncClient

from operator_day.main import create_app


def _headers(role: str = "owner") -> dict[str, str]:
    return {
        "X-Tenant-Id": "release-gate",
        "X-User-Id": "owner",
        "X-Role": role,
    }


def _has_git_remote() -> bool:
    config = Path(".git/config")
    return config.exists() and "[remote " in config.read_text(encoding="utf-8", errors="ignore")


async def test_release_gate_has_twenty_criteria_and_simulated_completion_path() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/release-gate?simulation=true", headers=_headers())

    assert response.status_code == 200
    body = response.json()
    criteria = body["criteria"]
    assert body["overallStatus"] == "ready_under_simulation"
    assert body["simulation"] is True
    assert len(criteria) == 20
    assert [item["id"] for item in criteria] == list(range(1, 21))
    assert body["summary"]["total"] == 20
    assert body["summary"]["blocked"] == 0
    assert body["summary"]["passed"] > 0
    assert body["summary"]["simulated"] > 0
    assert "real_marketplace_tokens" in body["liveBlockers"]
    assert ("git_remote_url" in body["liveBlockers"]) is (not _has_git_remote())
    assert body["proof"]["moduleCount"] == 23
    assert body["proof"]["skillsAndPlugins"] >= 30
    assert body["proof"]["checksPerAction"] == 10


async def test_release_gate_live_mode_blocks_without_external_keys_and_remote() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/release-gate?simulation=false", headers=_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["overallStatus"] == "blocked_for_real_use"
    assert body["simulation"] is False
    assert body["summary"]["blocked"] > 0
    assert "real_marketplace_tokens" in body["liveBlockers"]
    assert "prod_llm_gate" in body["liveBlockers"]
    assert ("git_remote_url" in body["liveBlockers"]) is (not _has_git_remote())


async def test_release_gate_is_owner_only() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/release-gate", headers=_headers(role="manager"))

    assert response.status_code == 403
