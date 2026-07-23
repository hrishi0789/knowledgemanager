"""
app/outbox/sweeper.py

Celery beat task that claims PENDING outbox events and dispatches them to
their routed Celery task(s).

Algorithm (02 §5.2 + §5.4):
  1. Claim up to OUTBOX_BATCH_SIZE PENDING rows using FOR UPDATE SKIP LOCKED
     → mark as PROCESSING atomically.
  2. For each claimed row: look up routing → send_task for each target.
  3. If dispatch fails: reset row back to PENDING immediately.
  4. Stuck-lock reclaim: rows stuck in PROCESSING for > 10 minutes
     are reset to PENDING on each tick.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select, text, update

from app.core.config import get_settings
from app.core.db import session_context
from app.db.models.outbox import OutboxEvent, OutboxStatus
from app.outbox.routing import EVENT_ROUTING
from app.workers.celery_app import celery_app

log = structlog.get_logger(__name__)
settings = get_settings()

_STUCK_THRESHOLD_MINUTES = 10


def _claim_pending(conn_str: str, batch_size: int) -> list[dict]:
    """
    Synchronous helper that claims PENDING events using SKIP LOCKED.
    Returns list of dicts: {id, event_type, payload}.
    Uses raw psycopg2 to keep the connection short-lived per tick.
    """
    import psycopg2
    import psycopg2.extras

    dsn = settings.postgres_sync_dsn
    with psycopg2.connect(dsn) as conn:
        conn.autocommit = False
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                UPDATE outbox_events
                SET status = 'PROCESSING',
                    locked_at = NOW(),
                    updated_at = NOW()
                WHERE id IN (
                    SELECT id FROM outbox_events
                    WHERE status = 'PENDING'
                    ORDER BY created_at ASC
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING id, event_type, payload
                """,
                (batch_size,),
            )
            rows = cur.fetchall()
            # Also reclaim stuck PROCESSING rows
            cur.execute(
                """
                UPDATE outbox_events
                SET status = 'PENDING',
                    locked_at = NULL,
                    updated_at = NOW()
                WHERE status = 'PROCESSING'
                  AND locked_at < NOW() - INTERVAL '%s minutes'
                """,
                (_STUCK_THRESHOLD_MINUTES,),
            )
            conn.commit()
    return [dict(r) for r in rows]


def _mark_completed(event_id: str) -> None:
    import psycopg2

    dsn = settings.postgres_sync_dsn
    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE outbox_events
                SET status = 'COMPLETED', updated_at = NOW()
                WHERE id = %s
                """,
                (event_id,),
            )
        conn.commit()


def _reset_to_pending(event_id: str, error_msg: str) -> None:
    import psycopg2

    dsn = settings.postgres_sync_dsn
    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE outbox_events
                SET status = CASE
                        WHEN retry_count + 1 >= max_retries THEN 'FAILED'
                        ELSE 'PENDING'
                    END,
                    retry_count = retry_count + 1,
                    locked_at = NULL,
                    error_log = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (error_msg[:2000], event_id),
            )
        conn.commit()


@celery_app.task(name="pkms.outbox.dispatch")
def dispatch_pending() -> int:
    """
    Claim up to ``OUTBOX_BATCH_SIZE`` PENDING events and route each to its
    Celery task(s). Returns the number of events claimed this tick.
    """
    batch_size = settings.outbox_batch_size
    rows = _claim_pending(settings.postgres_sync_dsn, batch_size)

    if not rows:
        # Avoid noisy logs every 2 seconds on idle queues
        return 0

    dispatched = 0
    for row in rows:
        event_id = str(row["id"])
        event_type: str = row["event_type"]
        payload: dict = row["payload"]

        task_names = EVENT_ROUTING.get(event_type, [])

        if not task_names:
            # Terminal event (e.g. document.indexed) — just mark complete
            _mark_completed(event_id)
            dispatched += 1
            continue

        all_sent = True
        for task_name in task_names:
            try:
                celery_app.send_task(
                    task_name,
                    args=[payload, event_id],
                    queue="classifier" if "classify" in task_name else "celery",
                )
            except Exception as exc:
                log.error(
                    "Failed to dispatch task",
                    task=task_name,
                    event_id=event_id,
                    error=str(exc),
                )
                _reset_to_pending(event_id, str(exc))
                all_sent = False
                break

        if all_sent:
            # For multi-task fan-out, the event is marked COMPLETED by the
            # first task that finishes. For terminal events or single-task
            # routes, we mark here.
            if len(task_names) == 1:
                # Single-task: sweeper marks; task uses its own completion
                pass  # task itself will mark COMPLETED
            dispatched += 1

    log.info("Outbox sweep complete", dispatched=dispatched, batch=len(rows))
    return dispatched
