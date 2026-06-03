from operator_day.workers.tasks import (
    _collect_morning_async,
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


async def test_collect_morning_async_persists_ranked_tasks() -> None:
    result = await _collect_morning_async("worker-seller", "worker-user", "owner", 3)

    assert result["tenant_id"] == "worker-seller"
    assert result["count"] == 3
    assert result["top"][0]["score"] >= result["top"][-1]["score"]
