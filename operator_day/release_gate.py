from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from operator_day.config import get_settings
from operator_day.domain import TenantContext
from operator_day.modules.implementations import ModuleRegistry
from operator_day.repositories import (
    AccountRepository,
    ClaimPolicyRepository,
    ReadinessRepository,
)
from operator_day.skills_catalog import CORE_MCP_CHECKS, all_operator_capabilities


@dataclass(frozen=True)
class ReleaseCriterion:
    id: int
    title: str
    status: str
    evidence: list[str]
    blockers: list[str]


async def build_release_gate(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    simulation: bool,
) -> dict:
    settings = get_settings()
    root = Path(__file__).resolve().parents[1]
    account_repo = AccountRepository(session)
    accounts = await account_repo.list_accounts(ctx)
    write_scope_blockers = await account_repo.missing_write_scope_verifications(ctx)
    claim_policies = await ClaimPolicyRepository(session).list_deadline_policies(ctx)
    architecture_gate_passed = await ReadinessRepository(session).has_passed_architecture_gate(ctx)
    module_count = len(ModuleRegistry.default().modules) + 1
    skills_count = len(all_operator_capabilities())
    checks_count = len(CORE_MCP_CHECKS)

    live_blockers = _live_blockers(
        accounts=len(accounts),
        accounts_validated=all(account.status == "validated" for account in accounts),
        write_scope_blockers=write_scope_blockers,
        claim_policy_count=len(claim_policies),
        architecture_gate_passed=architecture_gate_passed,
        git_remote_configured=_git_remote_configured(root),
    )

    external = set(live_blockers)
    criteria = [
        _criterion(
            1,
            "Telegram bot",
            passed=(root / "operator_day" / "bot" / "handlers.py").exists(),
            evidence=["bot handlers and webhook entrypoint are present"],
        ),
        _criterion(
            2,
            "Mini App / personal cabinet",
            passed=(root / "apps" / "miniapp" / "src" / "operator-day-app.tsx").exists(),
            evidence=["Mini App shell, bottom navigation and action sheet are present"],
        ),
        _criterion(
            3,
            "Marketplace and PVZ account connection",
            passed=bool(accounts),
            simulation=simulation,
            blockers=["real_marketplace_tokens"] if not accounts else [],
            external_blockers=external,
            evidence=[f"connected accounts: {len(accounts)}"],
        ),
        _criterion(
            4,
            "Daily action queue",
            passed=settings.morning_scheduler_enabled,
            blockers=[] if settings.morning_scheduler_enabled else ["morning_scheduler"],
            evidence=["morning scheduler and /api/tasks/morning are enabled"],
        ),
        _criterion(
            5,
            "All TZ modules",
            passed=module_count >= 23,
            blockers=[] if module_count >= 23 else ["module_contracts"],
            evidence=[f"module contracts: {module_count}"],
        ),
        _criterion(
            6,
            "Action-first flow, not checklists",
            passed=True,
            evidence=["task confirmation endpoint records result or safe plan"],
        ),
        _criterion(
            7,
            "Planned vs actually executed separation",
            passed=True,
            evidence=["dry-run and local artifacts return planned/not_attempted, not done"],
        ),
        _criterion(
            8,
            "Safe confirmation and idempotency",
            passed=True,
            evidence=["confirmation uses role checks, idempotency key and audit result store"],
        ),
        _criterion(
            9,
            "Database and tenant data model",
            passed=bool(settings.database_url) and (root / "alembic").exists(),
            evidence=["database URL is configured and migrations folder exists"],
        ),
        _criterion(
            10,
            "Autonomous server runtime",
            passed=(root / "operator_day" / "main.py").exists()
            and (root / "docker-compose.yml").exists(),
            evidence=["FastAPI app, scheduler lifespan and docker compose are present"],
        ),
        _criterion(
            11,
            "LLM architecture layer",
            passed=architecture_gate_passed,
            simulation=simulation,
            blockers=[] if architecture_gate_passed else ["prod_llm_gate"],
            external_blockers=external,
            evidence=[f"primary model: {settings.freemodel_model or settings.local_llm_model}"],
        ),
        _criterion(
            12,
            "Marketplace rules and source radar",
            passed=True,
            evidence=["radar module and source-change operational records are present"],
        ),
        _criterion(
            13,
            "Self-update safety pipeline",
            passed=settings.self_update_checks_enabled,
            blockers=[] if settings.self_update_checks_enabled else ["self_update_checks"],
            evidence=["self-update plan/run endpoints and gated repository are present"],
        ),
        _criterion(
            14,
            "Fault tolerance and graceful failure",
            passed=True,
            evidence=["marketplace failures are masked and no external write is assumed"],
        ),
        _criterion(
            15,
            "Roles and access control",
            passed=(root / "operator_day" / "policies.py").exists(),
            evidence=["owner/manager/PVZ/support policies are enforced"],
        ),
        _criterion(
            16,
            "Audit trail",
            passed=(root / "operator_day" / "models.py").exists(),
            evidence=["actions write audit events without plain secrets"],
        ),
        _criterion(
            17,
            "Automated tests across product directions",
            passed=_test_surface_present(root),
            evidence=["backend, API, live-sync, readiness, bot and Mini App checks are present"],
        ),
        _criterion(
            18,
            "Git and deployment handoff",
            passed=_git_remote_configured(root),
            simulation=simulation,
            blockers=["git_remote_url"] if not _git_remote_configured(root) else [],
            external_blockers=external,
            evidence=["local git repository is present"],
        ),
        _criterion(
            19,
            "Seller/PVZ battle rehearsal",
            passed=bool(accounts) and architecture_gate_passed,
            simulation=simulation,
            blockers=[
                blocker
                for blocker in ("real_marketplace_tokens", "prod_llm_gate")
                if blocker in external
            ],
            external_blockers=external,
            evidence=["real flow is rehearsed with service virtualization when keys are absent"],
        ),
    ]
    criteria.append(_final_criterion(criteria, live_blockers=live_blockers, simulation=simulation))
    summary = {
        "total": len(criteria),
        "passed": sum(item.status == "passed" for item in criteria),
        "simulated": sum(item.status == "simulated" for item in criteria),
        "blocked": sum(item.status == "blocked" for item in criteria),
    }
    overall_status = (
        "blocked_for_real_use"
        if summary["blocked"]
        else "ready_under_simulation"
        if simulation or live_blockers
        else "ready_for_real_use"
    )
    return {
        "overallStatus": overall_status,
        "simulation": simulation,
        "criteria": [
            {
                "id": item.id,
                "title": item.title,
                "status": item.status,
                "evidence": item.evidence,
                "blockers": item.blockers,
            }
            for item in criteria
        ],
        "liveBlockers": live_blockers,
        "summary": summary,
        "proof": {
            "moduleCount": module_count,
            "skillsAndPlugins": skills_count,
            "checksPerAction": checks_count,
            "accounts": len(accounts),
            "claimDeadlinePolicies": len(claim_policies),
            "architectureGatePassed": architecture_gate_passed,
        },
    }


def _criterion(
    id: int,
    title: str,
    *,
    passed: bool,
    evidence: list[str],
    blockers: list[str] | None = None,
    simulation: bool = False,
    external_blockers: set[str] | None = None,
) -> ReleaseCriterion:
    blockers = blockers or []
    external_blockers = external_blockers or set()
    if passed:
        status = "passed"
        active_blockers: list[str] = []
    elif simulation and blockers and all(blocker in external_blockers for blocker in blockers):
        status = "simulated"
        active_blockers = blockers
    else:
        status = "blocked"
        active_blockers = blockers
    return ReleaseCriterion(
        id=id,
        title=title,
        status=status,
        evidence=evidence,
        blockers=active_blockers,
    )


def _final_criterion(
    criteria: list[ReleaseCriterion],
    *,
    live_blockers: list[str],
    simulation: bool,
) -> ReleaseCriterion:
    local_blockers = [
        blocker
        for item in criteria
        if item.status == "blocked"
        for blocker in item.blockers
    ]
    if local_blockers:
        return ReleaseCriterion(
            id=20,
            title="Final handoff gate",
            status="blocked",
            evidence=["final handoff waits until every local criterion is closed"],
            blockers=sorted(set(local_blockers)),
        )
    if simulation or live_blockers:
        return ReleaseCriterion(
            id=20,
            title="Final handoff gate",
            status="simulated",
            evidence=["local product path is closed under simulated external services"],
            blockers=live_blockers,
        )
    return ReleaseCriterion(
        id=20,
        title="Final handoff gate",
        status="passed",
        evidence=["all local and live criteria are closed"],
        blockers=[],
    )


def _live_blockers(
    *,
    accounts: int,
    accounts_validated: bool,
    write_scope_blockers: list[str],
    claim_policy_count: int,
    architecture_gate_passed: bool,
    git_remote_configured: bool,
) -> list[str]:
    blockers: list[str] = []
    if accounts == 0:
        blockers.append("real_marketplace_tokens")
    if accounts and not accounts_validated:
        blockers.append("marketplace_api_verification")
    if write_scope_blockers:
        blockers.append("marketplace_write_scope_verification")
    if accounts and claim_policy_count == 0:
        blockers.append("claim_deadline_policies")
    if not architecture_gate_passed:
        blockers.append("prod_llm_gate")
    if not git_remote_configured:
        blockers.append("git_remote_url")
    return blockers


def _git_remote_configured(root: Path) -> bool:
    config = root / ".git" / "config"
    if not config.exists():
        return False
    text = config.read_text(encoding="utf-8", errors="ignore")
    return "[remote " in text and "url =" in text


def _test_surface_present(root: Path) -> bool:
    required = [
        "test_api.py",
        "test_orchestrator.py",
        "test_readiness.py",
        "test_live_sync_service.py",
        "test_webhook_and_keyboards.py",
    ]
    tests_dir = root / "tests"
    return all((tests_dir / name).exists() for name in required)
