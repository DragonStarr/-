from __future__ import annotations

from operator_day.connectors.replay import ReplayHub
from operator_day.domain import ActionResult, ActionRisk, TaskAction, TaskStatus, TenantContext
from operator_day.execution.lifecycle import action_lifecycle
from operator_day.modules.base import OperatorModule
from operator_day.modules.implementations import ModuleRegistry


class MorningOrchestrator:
    def __init__(
        self, registry: ModuleRegistry | None = None, replay: ReplayHub | None = None
    ) -> None:
        self.registry = registry or ModuleRegistry.default()
        self.replay = replay or ReplayHub()
        self._tasks: dict[str, TaskAction] = {}

    async def collect_all(self, ctx: TenantContext) -> list[TaskAction]:
        tasks: list[TaskAction] = []
        for module in self.registry.modules:
            tasks.extend(await module.collect_actions(ctx, self.replay))
        self._score_tasks(tasks)
        tasks.sort(
            key=lambda task: (
                task.score,
                task.priority,
            ),
            reverse=True,
        )
        for task in tasks:
            task.status = (
                TaskStatus.WAITING_CONFIRMATION if task.confirm_required() else TaskStatus.NEW
            )
            self._tasks[task.task_id] = task
        return tasks

    async def morning_top(self, ctx: TenantContext, *, limit: int = 5) -> list[TaskAction]:
        tasks = await self.collect_all(ctx)
        return tasks[:limit]

    async def confirm(self, ctx: TenantContext, task_id: str) -> ActionResult:
        task = self._tasks[task_id]
        return await self.execute_prepared(ctx, task)

    async def execute_prepared(self, ctx: TenantContext, task: TaskAction) -> ActionResult:
        module = next(item for item in self.registry.modules if item.module_id == task.module_id)
        task.status = (
            TaskStatus.FAILED
            if module.__class__.execute is OperatorModule.execute
            else TaskStatus.ESCALATED
            if task.risk == ActionRisk.HUMAN
            else TaskStatus.DONE
        )
        result = await module.execute(ctx, task, self.replay)
        task.status = result.status
        audit_event = dict(result.audit_event)
        audit_event.setdefault("execution_lifecycle", action_lifecycle(task, audit_event))
        return ActionResult(
            task_id=result.task_id,
            status=result.status,
            user_text=result.user_text,
            audit_event=audit_event,
        )

    def get_task(self, task_id: str) -> TaskAction:
        return self._tasks[task_id]

    @staticmethod
    def _score_tasks(tasks: list[TaskAction]) -> None:
        max_money = max((abs(task.money_effect) for task in tasks), default=0) or 1
        for task in tasks:
            money = min(abs(task.money_effect) / max_money, 1)
            urgency = max(
                max(0, min(task.urgency, 1)),
                1.0 if task.has_near_deadline() else 0.0,
            )
            risk = {
                ActionRisk.SAFE: 0.2,
                ActionRisk.CONFIRM: 0.6,
                ActionRisk.HUMAN: 0.9,
            }[task.risk]
            task.score = (
                0.40 * money
                + 0.25 * urgency
                + 0.20 * risk
                + 0.15 * max(0, min(task.confidence, 1))
            )
