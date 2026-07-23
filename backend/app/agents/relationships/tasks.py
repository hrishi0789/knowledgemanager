"""
app/agents/relationships/tasks.py

Celery task: extract_triples

Runs coreference resolution → SVO extraction → Neo4j write
for all chunks of a document. Triggered on document.chunked event.
"""

from __future__ import annotations

import asyncio
import uuid

import structlog

from app.core.config import get_settings
from app.core.logging import set_trace_id
from app.workers.celery_app import celery_app

log = structlog.get_logger(__name__)
settings = get_settings()


def _mark_event(event_id: str, status: str, error_msg: str | None = None) -> None:
    import psycopg2

    sql = (
        "UPDATE outbox_events SET status=%s, updated_at=NOW(), error_log=%s WHERE id=%s"
        if error_msg
        else "UPDATE outbox_events SET status=%s, updated_at=NOW() WHERE id=%s"
    )
    with psycopg2.connect(settings.postgres_sync_dsn) as conn:
        with conn.cursor() as cur:
            args = (status, error_msg[:2000], event_id) if error_msg else (status, event_id)
            cur.execute(sql, args)
        conn.commit()


@celery_app.task(
    name="pkms.relationships.extract_triples",
    bind=True,
    max_retries=3,
)
def extract_triples(self, payload: dict, event_id: str) -> None:
    """
    Extract SVO triples from all chunks of a document and write to Neo4j.

    Payload: {document_id, user_id}
    """
    set_trace_id(event_id)
    document_id = uuid.UUID(payload["document_id"])

    async def _run_async() -> None:
        from sqlalchemy import select

        from app.agents.relationships.coref import resolve_coreferences
        from app.agents.relationships.extract import extract_triples_from_text
        from app.agents.relationships.writer import write_triples_to_neo4j
        from app.core.db import session_context
        from app.db.models.chunk import Chunk
        from app.db.models.document import Document

        async with session_context() as db:
            result = await db.execute(
                select(Document).where(Document.id == document_id)
            )
            doc = result.scalar_one_or_none()
            if not doc:
                log.warning("Document not found for triple extraction", id=str(document_id))
                return

            chunks_result = await db.execute(
                select(Chunk)
                .where(Chunk.document_id == document_id)
                .order_by(Chunk.chunk_index)
            )
            chunks = chunks_result.scalars().all()

            if not chunks:
                log.info("No chunks to process", document_id=str(document_id))
                return

            for chunk in chunks:
                try:
                    # Coreference resolution per chunk (safe default for 4 GB budget)
                    resolved = resolve_coreferences(chunk.text)
                    triples = extract_triples_from_text(resolved, max_syntactic_distance=4)

                    write_triples_to_neo4j(
                        document_id=str(doc.id),
                        document_title=doc.title,
                        document_category=doc.category,
                        user_id=str(doc.user_id),
                        chunk_id=str(chunk.id),
                        triples=triples,
                    )
                except Exception as chunk_exc:
                    # Per-chunk failure is non-fatal — log and continue
                    log.error(
                        "Triple extraction failed for chunk",
                        chunk_id=str(chunk.id),
                        error=str(chunk_exc),
                    )

            log.info(
                "Triple extraction complete",
                document_id=str(document_id),
                chunk_count=len(chunks),
            )

    try:
        asyncio.get_event_loop().run_until_complete(_run_async())
        _mark_event(event_id, "COMPLETED")
    except Exception as exc:
        log.error(
            "extract_triples task failed",
            document_id=str(document_id),
            error=str(exc),
        )
        try:
            raise self.retry(exc=exc, countdown=10)
        except self.MaxRetriesExceededError:
            _mark_event(event_id, "FAILED", str(exc))
