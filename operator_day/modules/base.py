from __future__ import annotations

from abc import ABC, abstractmethod

from operator_day.connectors.replay import ReplayHub
from operator_day.domain import (
    ActionResult,
    ActionRisk,
    ModuleId,
    TaskAction,
    TaskStatus,
    TenantContext,
)


class OperatorModule(ABC):
    module_id: ModuleId
    title: str

    @abstractmethod
    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        """Collect ready-to-confirm actions for the morning operator queue."""

    async def execute(
        self, ctx: TenantContext, task: TaskAction, replay: ReplayHub
    ) -> ActionResult:
        artifact = await replay.record_operator_artifact(
            ctx,
            task.payload,
            module_id=self.module_id.value,
            task_id=task.task_id,
        )
        status = TaskStatus.ESCALATED if task.risk == ActionRisk.HUMAN else TaskStatus.PLANNED
        user_text = (
            "Передал человеку и сохранил план в системе. В личных кабинетах ничего не менял."
            if task.risk == ActionRisk.HUMAN
            else "Записал рабочий план в системе; внешние кабинеты не менял."
        )
        return ActionResult(
            task_id=task.task_id,
            status=status,
            user_text=user_text,
            audit_event={
                "tenant_id": ctx.tenant_id,
                "user_id": ctx.user_id,
                "module": self.module_id.value,
                "task_id": task.task_id,
                "payload": task.payload,
                "action": "local_artifact_recorded",
                "connector_status": artifact["status"],
                "artifact": artifact,
                "marketplace_write": "not_attempted",
            },
        )
