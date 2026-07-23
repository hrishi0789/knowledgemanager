"""
app/agents/kg_maintenance/tasks.py

Periodic Celery task: pkms.kg.maintain
Runs all graph hygiene operations with a Redis lock to prevent overlap.
"""

from __future__ import annotations

import structlog

from app.core.config import get_settings
from app.workers.celery_app import celery_app

log = structlog.get_logger(__name__)
settings = get_settings()

_REDIS_LOCK_KEY = "lock:kg_maintain"
_LOCK_TIMEOUT_SECONDS = settings.kg_maintain_seconds - 10  # expire before next tick


@celery_app.task(name="pkms.kg.maintain")
def maintain_graph(payload: dict | None = None, event_id: str | None = None) -> dict:
    """
    Run all KG maintenance operations. Returns a summary dict.
    Acquires a Redis lock to prevent overlapping runs.
    """
    import redis as redis_lib

    r = redis_lib.from_url(settings.redis_url, decode_responses=True)

    # Acquire non-blocking lock
    acquired = r.set(
        _REDIS_LOCK_KEY,
        "1",
        nx=True,
        ex=max(_LOCK_TIMEOUT_SECONDS, 60),
    )
    if not acquired:
        log.debug("KG maintenance skipped — lock held")
        return {"skipped": True}

    summary: dict = {}
    try:
        from app.agents.kg_maintenance.resolution import (
            derive_cooccurrence_weights,
            detect_prerequisite_cycles,
            remove_orphans,
            resolve_entities,
            update_pagerank,
        )
        from app.services.neo4j import get_driver

        driver = get_driver()

        summary["entity_merges"] = resolve_entities(driver)
        summary["cooccurrence_updated"] = derive_cooccurrence_weights(driver)
        summary["orphans_removed"] = remove_orphans(driver)
        cycles = detect_prerequisite_cycles(driver)
        summary["cycles_detected"] = len(cycles)
        summary["pagerank_nodes"] = update_pagerank(driver)

        log.info("KG maintenance complete", **summary)
    except Exception as exc:
        log.error("KG maintenance failed", error=str(exc))
        summary["error"] = str(exc)
    finally:
        r.delete(_REDIS_LOCK_KEY)

    return summary
