"""
app/agents/analytics/tasks.py

Periodic Celery task: recompute_prerequisites (09)
"""

from __future__ import annotations

import structlog

from app.core.config import get_settings
from app.workers.celery_app import celery_app

log = structlog.get_logger(__name__)
settings = get_settings()

_REDIS_LOCK_KEY = "lock:analytics_prereq"


@celery_app.task(name="pkms.analytics.recompute_prerequisites")
def recompute_prerequisites(payload=None, event_id=None) -> dict:
    """Recompute all PREREQUISITE_OF edges idempotently."""
    import redis as redis_lib

    r = redis_lib.from_url(settings.redis_url, decode_responses=True)
    acquired = r.set(
        _REDIS_LOCK_KEY,
        "1",
        nx=True,
        ex=max(settings.analytics_seconds - 10, 60),
    )
    if not acquired:
        log.debug("Analytics recompute skipped — lock held")
        return {"skipped": True}

    try:
        from app.agents.analytics.refd import build_prerequisite_edges
        from app.services.neo4j import get_driver

        driver = get_driver()
        written = build_prerequisite_edges(driver)
        log.info("Analytics recompute complete", edges=written)
        return {"edges_written": written}
    except Exception as exc:
        log.error("Analytics recompute failed", error=str(exc))
        return {"error": str(exc)}
    finally:
        r.delete(_REDIS_LOCK_KEY)
