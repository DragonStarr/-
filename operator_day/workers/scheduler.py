from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy import select

from operator_day.brain.orchestrator import MorningOrchestrator
from operator_day.connectors.replay import DatabaseReplayHub
from operator_day.db import ensure_local_database, get_sessionmaker
from operator_day.domain import Role, TaskAction, TenantContext
from operator_day.models import AuditLog, User
from operator_day.repositories import TaskRepository

MorningDigestNotifier = Callable[[str, list[TaskAction]], Awaitable[None]]


@dataclass(frozen=True)
class SchedulerRunResult:
    tenants: int
    tasks: int
    notifications: int = 0
    notification_errors: int = 0


async def run_morning_scheduler(
    *,
    interval_seconds: int,
    limit: int,
    notifier: MorningDigestNotifier | None = None,
    stop_event: asyncio.Event | None = None,
) -> None:
    await ensure_local_database()
    signal = stop_event or asyncio.Event()
    while not signal.is_set():
        await collect_due_morning(limit=limit, notifier=notifier)
        try:
            await asyncio.wait_for(signal.wait(), timeout=max(interval_seconds, 60))
        except TimeoutError:
            continue


async def collect_due_morning(
    *,
    limit: int,
    notifier: MorningDigestNotifier | None = None,
) -> SchedulerRunResult:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        users = (
            await session.execute(
                select(User)
                .where(User.role.in_([Role.OWNER.value, Role.MANAGER.value]))
                .order_by(User.tenant_id.asc(), User.id.asc())
            )
        ).scalars().all()

    users_by_tenant: dict[str, list[User]] = {}
    for user in users:
        users_by_tenant.setdefault(user.tenant_id, []).append(user)
    total_tasks = 0
    notifications = 0
    notification_errors = 0
    for tenant_users in users_by_tenant.values():
        user = tenant_users[0]
        ctx = TenantContext(tenant_id=user.tenant_id, user_id=user.id, role=Role(user.role))
        async with sessionmaker() as session:
            tasks = await MorningOrchestrator(
                replay=DatabaseReplayHub(session, ctx)
            ).morning_top(ctx, limit=limit)
            await TaskRepository(session).save_tasks(ctx, tasks)
            notified = 0
            failed = 0
            if notifier and tasks:
                for recipient in tenant_users:
                    try:
                        await notifier(recipient.tg_id, tasks)
                        notified += 1
                    except Exception:
                        failed += 1
            session.add(
                AuditLog(
                    tenant_id=ctx.tenant_id,
                    user_id=ctx.user_id,
                    action="morning_scheduler_collected",
                    before_after={
                        "task_count": len(tasks),
                        "limit": limit,
                        "mode": "local_queue",
                        "telegram_notifications": notified,
                        "telegram_notification_errors": failed,
                    },
                )
            )
            await session.commit()
        total_tasks += len(tasks)
        notifications += notified
        notification_errors += failed

    return SchedulerRunResult(
        tenants=len(users_by_tenant),
        tasks=total_tasks,
        notifications=notifications,
        notification_errors=notification_errors,
    )
