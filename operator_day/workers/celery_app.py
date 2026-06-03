from __future__ import annotations

from celery import Celery

from operator_day.config import get_settings

settings = get_settings()

celery_app = Celery(
    "operator_day",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["operator_day.workers.tasks"],
)

celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    timezone="Europe/Moscow",
)
