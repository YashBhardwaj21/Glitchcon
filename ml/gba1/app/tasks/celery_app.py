"""
gba1/app/tasks/celery_app.py
-----------------------------
Celery application instance for GBA1.
Uses separate Redis DB indices (3, 4) to avoid conflicts with
the moderation service which uses indices 1 and 2.
"""
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "gba1",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.moderation_task"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Retry failed tasks up to 3 times with exponential backoff
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
)
