from __future__ import annotations

from abc import ABC, abstractmethod

from operator_day.connectors.replay import ReplayHub
from operator_day.domain import (
    ActionResult,
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
        return ActionResult(
            task_id=task.task_id,
            status=TaskStatus.FAILED,
            user_text=(
                "Это действие пока не исполняется автоматически. "
                "Система сохранила проверку и не внесла изменений в кабинеты."
            ),
            audit_event={
                "tenant_id": ctx.tenant_id,
                "user_id": ctx.user_id,
                "module": self.module_id.value,
                "task_id": task.task_id,
                "payload": task.payload,
                "action": "execution_not_available",
                "connector_status": "not_executable_yet",
            },
        )
