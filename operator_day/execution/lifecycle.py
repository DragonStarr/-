from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from operator_day.domain import ActionRisk, TaskAction, TaskStatus


def action_lifecycle(task: TaskAction, audit_event: dict[str, Any]) -> dict[str, Any]:
    marketplace = audit_event.get("marketplace_operation") or {}
    if task.risk == ActionRisk.HUMAN or task.status == TaskStatus.ESCALATED:
        execution_stage = "human_escalated"
    elif marketplace.get("live") is True:
        execution_stage = "marketplace_executed"
    elif marketplace:
        execution_stage = "marketplace_planned"
    else:
        execution_stage = "local_action_recorded"
    now = datetime.now(UTC).isoformat()
    return {
        "workflow": "operator_day_confirmed_action",
        "checkpointId": f"{task.task_id}:{task.status.value}",
        "threadId": task.task_id,
        "humanInTheLoop": task.confirm_required(),
        "stages": [
            {"name": "collected", "status": "pass", "at": task.created_at.isoformat()},
            {"name": "confirmed", "status": "pass", "at": now},
            {"name": execution_stage, "status": "pass", "at": now},
            {"name": "audited", "status": "pending_write", "at": now},
        ],
        "rollback": rollback_hint(task, marketplace),
    }


def rollback_hint(task: TaskAction, marketplace: dict[str, Any]) -> dict[str, str]:
    if marketplace.get("live") is True:
        return {
            "mode": "compensating_action_required",
            "reason": "live marketplace write was executed",
        }
    if task.risk == ActionRisk.HUMAN:
        return {"mode": "none", "reason": "action was escalated, not executed"}
    return {"mode": "discard_plan", "reason": "only a dry-run or local plan exists"}
