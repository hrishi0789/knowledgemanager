"""
app/outbox/writer.py

Outbox event emitter. Called inside the caller's active transaction.

Contract (02 §2.1):
  - MUST NOT open its own session or commit.
  - The caller's session commits both the business row and the event atomically.
  - Returns the new event's UUID for tracing.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.outbox import OutboxEvent, OutboxStatus


async def emit_event(
    session: AsyncSession,
    event_type: str,
    payload: dict,
    max_retries: int = 5,
) -> uuid.UUID:
    """
    Insert an ``OutboxEvent`` row using the **caller's existing session**.

    This function MUST be called inside an active transaction. It flushes
    the row to register it in the transaction but does NOT commit — the
    caller is responsible for committing so the business row and outbox row
    are atomic (both committed or both rolled back).

    Parameters
    ----------
    session:
        The caller's active ``AsyncSession``. Must already have a
        transaction in progress.
    event_type:
        The canonical event type string (see routing.py for valid values).
    payload:
        A small JSON-serialisable dict containing only IDs, never raw data.
    max_retries:
        Maximum retry attempts before the event is marked FAILED.

    Returns
    -------
    uuid.UUID:
        The newly created event's primary key (for logging / tracing).
    """
    event = OutboxEvent(
        event_type=event_type,
        payload=payload,
        status=OutboxStatus.PENDING,
        retry_count=0,
        max_retries=max_retries,
    )
    session.add(event)
    # Flush to assign a server-generated UUID but do NOT commit.
    await session.flush([event])
    return event.id  # type: ignore[return-value]
