from __future__ import annotations

from operator_day.modules.implementations import ModuleRegistry
from operator_day.skills_catalog import CORE_MCP_CHECKS, all_operator_capabilities


def render_prometheus_metrics(*, readiness_status: str = "unknown") -> str:
    module_count = len(ModuleRegistry.default().modules) + 1
    skill_count = len(all_operator_capabilities())
    check_count = len(CORE_MCP_CHECKS)
    ready_value = 1 if readiness_status == "ready_for_live_pilot" else 0
    lines = [
        "# HELP operator_day_modules_total Registered operator modules.",
        "# TYPE operator_day_modules_total gauge",
        f"operator_day_modules_total {module_count}",
        "# HELP operator_day_capabilities_total Skills and plugins attached to every action.",
        "# TYPE operator_day_capabilities_total gauge",
        f"operator_day_capabilities_total {skill_count}",
        "# HELP operator_day_mcp_checks_per_action Required MCP-style checks per action.",
        "# TYPE operator_day_mcp_checks_per_action gauge",
        f"operator_day_mcp_checks_per_action {check_count}",
        "# HELP operator_day_ready_for_live_pilot Live pilot readiness flag.",
        "# TYPE operator_day_ready_for_live_pilot gauge",
        f"operator_day_ready_for_live_pilot {ready_value}",
    ]
    return "\n".join(lines) + "\n"
