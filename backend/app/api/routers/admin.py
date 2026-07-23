from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.db import get_session
from app.db.models.outbox import OutboxStatus
from app.db.models.user import User
from app.schemas import EvaluationReport, HealthResponse, OutboxSummary, StoreHealth

router = APIRouter(prefix="/admin", tags=["admin"])
log = structlog.get_logger(__name__)


@router.get("/health", response_model=HealthResponse)
async def health(
    db: AsyncSession = Depends(get_session),
) -> HealthResponse:
    """Return health status of all downstream stores. Does not require auth."""
    from sqlalchemy import text

    from app.core.config import get_settings

    settings = get_settings()

    # Postgres: db session is already active
    pg_ok = True
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        pg_ok = False

    # Chroma
    chroma_ok = True
    try:
        from app.services.chroma import get_collection

        get_collection().count()
    except Exception:
        chroma_ok = False

    # Neo4j
    neo4j_ok = True
    try:
        from app.services.neo4j import run_query

        run_query("RETURN 1")
    except Exception:
        neo4j_ok = False

    # Redis
    redis_ok = True
    try:
        import redis as redis_lib

        r = redis_lib.from_url(settings.redis_url, decode_responses=True, socket_timeout=2)
        r.ping()
    except Exception:
        redis_ok = False

    all_ok = all([pg_ok, chroma_ok, neo4j_ok, redis_ok])
    any_ok = any([pg_ok, chroma_ok, neo4j_ok, redis_ok])

    return HealthResponse(
        status="ok" if all_ok else ("degraded" if any_ok else "down"),
        stores=StoreHealth(
            postgres=pg_ok,
            chroma=chroma_ok,
            neo4j=neo4j_ok,
            redis=redis_ok,
        ),
        version="1.0.0",
    )


@router.get("/outbox", response_model=OutboxSummary)
async def outbox_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> OutboxSummary:
    """Return current outbox queue depth per status."""
    from sqlalchemy import func
    from app.db.models.outbox import OutboxEvent

    result = await db.execute(
        select(OutboxEvent.status, func.count())
        .group_by(OutboxEvent.status)
    )
    counts = {row[0]: row[1] for row in result}

    return OutboxSummary(
        pending=counts.get(OutboxStatus.PENDING, 0),
        processing=counts.get(OutboxStatus.PROCESSING, 0),
        failed=counts.get(OutboxStatus.FAILED, 0),
    )


@router.post("/evaluation", response_model=EvaluationReport)
async def run_evaluation(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> EvaluationReport:
    """Trigger the full evaluation harness and return the report."""
    from app.evaluation.harness import run_full_evaluation

    report = await run_full_evaluation(db=db, user_id=str(current_user.id))
    return report
