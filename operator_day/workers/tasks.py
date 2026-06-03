from __future__ import annotations

import asyncio

from operator_day.brain.orchestrator import MorningOrchestrator
from operator_day.connectors.live_sync import sync_catalog_for_account
from operator_day.db import ensure_local_database, get_sessionmaker
from operator_day.domain import Role, TenantContext
from operator_day.repositories import TaskRepository
from operator_day.workers.celery_app import celery_app


@celery_app.task(
    name="operator_day.collect_morning",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3},
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def collect_morning(
    tenant_id: str,
    user_id: str = "worker",
    role: str = Role.OWNER.value,
    limit: int = 5,
) -> dict:
    return asyncio.run(_collect_morning_async(tenant_id, user_id, role, limit))


@celery_app.task(
    name="operator_day.sync_catalog",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3},
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def sync_catalog(
    tenant_id: str,
    account_id: str,
    user_id: str = "worker",
    role: str = Role.OWNER.value,
) -> dict:
    return asyncio.run(_sync_catalog_async(tenant_id, account_id, user_id, role))


@celery_app.task(
    name="operator_day.sync_ozon_catalog",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3},
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def sync_ozon_catalog(
    tenant_id: str,
    account_id: str,
    user_id: str = "worker",
    role: str = Role.OWNER.value,
) -> dict:
    return asyncio.run(_sync_catalog_async(tenant_id, account_id, user_id, role))


async def _collect_morning_async(
    tenant_id: str,
    user_id: str,
    role: str,
    limit: int,
) -> dict:
    await ensure_local_database()
    ctx = TenantContext(tenant_id=tenant_id, user_id=user_id, role=Role(role))
    tasks = await MorningOrchestrator().morning_top(ctx, limit=limit)
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        await TaskRepository(session).save_tasks(ctx, tasks)
    return {
        "tenant_id": tenant_id,
        "status": "saved",
        "count": len(tasks),
        "top": [
            {
                "task_id": task.task_id,
                "module_id": task.module_id.value,
                "score": round(task.score, 4),
                "risk": task.risk.value,
            }
            for task in tasks
        ],
    }


async def _sync_catalog_async(
    tenant_id: str,
    account_id: str,
    user_id: str,
    role: str,
) -> dict:
    await ensure_local_database()
    ctx = TenantContext(tenant_id=tenant_id, user_id=user_id, role=Role(role))
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        return await sync_catalog_for_account(session, ctx, account_id)


async def _sync_ozon_catalog_async(
    tenant_id: str,
    account_id: str,
    user_id: str,
    role: str,
) -> dict:
    return await _sync_catalog_async(tenant_id, account_id, user_id, role)
