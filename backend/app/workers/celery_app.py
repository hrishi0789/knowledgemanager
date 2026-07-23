"""
app/workers/celery_app.py

Celery application instance with:
  - Redis as broker AND result backend
  - Beat schedule for periodic tasks (outbox sweeper, KG maintenance, analytics)
  - Task routing: 'classifier' queue is single-concurrency (--concurrency=1)
    to prevent concurrent partial_fit race conditions.
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "pkms",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.outbox.sweeper",
        "app.agents.ingestion.tasks",
        "app.agents.classification.tasks",
        "app.agents.relationships.tasks",
        "app.agents.kg_maintenance.tasks",
        "app.agents.dedup.tasks",
        "app.agents.analytics.tasks",
    ],
)

celery_app.conf.update(
    # Serialisation
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Reliability
    task_acks_late=True,           # acknowledge after the task succeeds
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # fair distribution; avoids task hoarding
    # Result expiry (we don't rely on stored results — outbox tracks state)
    result_expires=3600,
    # Routing: classifier tasks go to the single-concurrency queue
    task_routes={
        "pkms.classification.classify_chunks": {"queue": "classifier"},
    },
    # Beat schedule
    beat_schedule={
        "outbox-dispatch": {
            "task": "pkms.outbox.dispatch",
            "schedule": settings.outbox_sweep_seconds,
        },
        "kg-maintain": {
            "task": "pkms.kg.maintain",
            "schedule": settings.kg_maintain_seconds,
        },
        "analytics-recompute": {
            "task": "pkms.analytics.recompute_prerequisites",
            "schedule": settings.analytics_seconds,
        },
    },
)
