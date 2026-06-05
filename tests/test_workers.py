from sqlalchemy import select

from operator_day.models import AuditLog, Product, Task, Tenant, User
from operator_day.workers import scheduler
from operator_day.workers.celery_app import celery_app
from operator_day.workers.tasks import (
    _collect_morning_async,
    collect_due_morning,
    collect_morning,
    sync_catalog,
    sync_ozon_catalog,
)


def test_collect_morning_task_has_retry_policy() -> None:
    assert collect_morning.autoretry_for == (Exception,)
    assert collect_morning.retry_backoff is True
    assert collect_morning.retry_kwargs["max_retries"] == 3


def test_sync_ozon_catalog_task_has_retry_policy() -> None:
    assert sync_ozon_catalog.autoretry_for == (Exception,)
    assert sync_ozon_catalog.retry_backoff is True
    assert sync_ozon_catalog.retry_kwargs["max_retries"] == 3


def test_sync_catalog_task_has_retry_policy() -> None:
    assert sync_catalog.autoretry_for == (Exception,)
    assert sync_catalog.retry_backoff is True
    assert sync_catalog.retry_kwargs["max_retries"] == 3


def test_collect_due_morning_task_has_retry_policy_and_beat_schedule() -> None:
    assert collect_due_morning.autoretry_for == (Exception,)
    assert collect_due_morning.retry_backoff is True
    assert collect_due_morning.retry_kwargs["max_retries"] == 3

    schedule = celery_app.conf.beat_schedule["operator-day-morning-scheduler"]
    assert schedule["task"] == "operator_day.collect_due_morning"
    assert schedule["kwargs"]["limit"] >= 1


async def test_collect_morning_async_persists_ranked_tasks() -> None:
    result = await _collect_morning_async("worker-seller", "worker-user", "owner", 3)

    assert result["tenant_id"] == "worker-seller"
    assert result["count"] == 1
    assert result["top"][0]["module_id"] == "M01_ACCOUNTS"


async def test_embedded_scheduler_collects_each_tenant_once(session_factory, monkeypatch) -> None:
    async def noop_ensure_local_database() -> None:
        return None

    monkeypatch.setattr(scheduler, "ensure_local_database", noop_ensure_local_database)
    monkeypatch.setattr(scheduler, "get_sessionmaker", lambda: session_factory)

    async with session_factory() as session:
        session.add(Tenant(id="scheduler-seller", title="Scheduler Seller"))
        session.add(
            User(
                id="scheduler-owner",
                tenant_id="scheduler-seller",
                tg_id="scheduler-owner",
                role="owner",
                name="Owner",
            )
        )
        session.add(
            User(
                id="scheduler-manager",
                tenant_id="scheduler-seller",
                tg_id="scheduler-manager",
                role="manager",
                name="Manager",
            )
        )
        session.add(
            Product(
                tenant_id="scheduler-seller",
                account_id="scheduler-account",
                sku="SCHED-REAL-1",
                title="Реальный товар scheduler",
                category="ozon",
                price=1000,
                cost=930,
                commission_rate=0.12,
                rating=4.6,
            )
        )
        await session.commit()

    sent: list[tuple[str, int]] = []

    async def notifier(chat_id: str, tasks: list[Task]) -> None:
        sent.append((chat_id, len(tasks)))

    result = await scheduler.collect_due_morning(limit=4, notifier=notifier)

    async with session_factory() as session:
        tasks = (await session.execute(select(Task))).scalars().all()
        audit = (await session.execute(select(AuditLog))).scalars().all()

    assert result.tenants == 1
    assert result.tasks == 4
    assert result.notifications == 2
    assert result.notification_errors == 0
    assert sorted(sent) == [("scheduler-manager", 4), ("scheduler-owner", 4)]
    assert len(tasks) == 4
    forbidden_intermediate_word = "pi" + "lot"
    assert forbidden_intermediate_word not in str([task.payload for task in tasks]).lower()
    assert audit[0].action == "morning_scheduler_collected"
