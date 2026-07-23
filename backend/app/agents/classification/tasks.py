"""
app/agents/classification/tasks.py

Celery task: classify_chunks

Runs on the dedicated 'classifier' queue (single concurrency) to
prevent concurrent partial_fit corruption. Uses a Postgres advisory
lock as a belt-and-suspenders guard.

Payload: {document_id, user_id}
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

_MAX_SAMPLE_CHARS = 20_000   # cap on classification input length


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _mark_event(event_id: str, status: str, error_msg: str | None = None) -> None:
    import psycopg2

    sql = (
        "UPDATE outbox_events SET status=%s, updated_at=NOW(), error_log=%s WHERE id=%s"
        if error_msg
        else "UPDATE outbox_events SET status=%s, updated_at=NOW() WHERE id=%s"
    )
    with psycopg2.connect(settings.postgres_sync_dsn) as conn:
        with conn.cursor() as cur:
            if error_msg:
                cur.execute(sql, (status, error_msg[:2000], event_id))
            else:
                cur.execute(sql, (status, event_id))
        conn.commit()


@celery_app.task(
    name="pkms.classification.classify_chunks",
    bind=True,
    max_retries=3,
    queue="classifier",
)
def classify_chunks(self, payload: dict, event_id: str) -> None:
    set_trace_id(event_id)
    document_id = uuid.UUID(payload["document_id"])

    async def _run_async() -> None:
        from sqlalchemy import select, text

        from app.agents.classification.state import (
            add_replay,
            load_engine,
            sample_replay,
            save_engine,
        )
        from app.core.db import session_context
        from app.db.models.chunk import Chunk
        from app.db.models.document import Document, ExtractionStatus
        from app.services.chroma import get_collection

        async with session_context() as db:
            # Postgres advisory lock to prevent concurrent partial_fit
            lock_key = hash("classifier_state") & 0x7FFFFFFF
            await db.execute(text(f"SELECT pg_advisory_xact_lock({lock_key})"))

            result = await db.execute(
                select(Document).where(Document.id == document_id)
            )
            doc = result.scalar_one_or_none()
            if not doc:
                log.warning("Document not found for classification", id=str(document_id))
                return

            # Load chunks ordered by index
            chunks_result = await db.execute(
                select(Chunk)
                .where(Chunk.document_id == document_id)
                .order_by(Chunk.chunk_index)
            )
            chunks = chunks_result.scalars().all()

            if not chunks:
                doc.category = "Uncategorized"
                doc.category_conf = 0.0
                return

            # Build sample text: concatenate chunks up to limit
            sample_text = " ".join(c.text for c in chunks)[:_MAX_SAMPLE_CHARS]

            engine = await load_engine(db)
            result_dict = engine.infer_category(sample_text)
            category = result_dict["category"]
            confidence = result_dict["confidence"]

            doc.category = category
            doc.category_conf = confidence
            doc.status = ExtractionStatus.INDEXED

            # Learn from this sample (auto-label from the prediction itself)
            # Only learn if confidence is high enough to be trusted
            if engine.n_updates > 0 and confidence >= 0.6:
                replay = await sample_replay(db, settings.replay_mix)
                replay_texts = [t for _, t in replay]
                replay_labels = [l for l, _ in replay]
                engine.learn_incrementally(
                    [sample_text], [category],
                    replay_texts=replay_texts or None,
                    replay_labels=replay_labels or None,
                )
                await add_replay(db, category, sample_text[:1000])
                await save_engine(db, engine)

            # Denormalise category into Chroma metadata for filtering
            collection = get_collection()
            chunk_ids = [str(c.id) for c in chunks]
            # Update metadata: Chroma doesn't support bulk metadata update
            # so we re-upsert with updated metadata only
            existing = collection.get(ids=chunk_ids, include=["metadatas", "embeddings", "documents"])
            if existing["ids"]:
                updated_metadatas = []
                for meta in existing["metadatas"]:
                    m = dict(meta)
                    m["category"] = category
                    updated_metadatas.append(m)
                collection.upsert(
                    ids=existing["ids"],
                    embeddings=existing["embeddings"],
                    metadatas=updated_metadatas,
                    documents=existing["documents"],
                )

            log.info(
                "Classification complete",
                document_id=str(document_id),
                category=category,
                confidence=confidence,
            )

    try:
        _run(_run_async())
        _mark_event(event_id, "COMPLETED")
    except Exception as exc:
        log.error(
            "Classification failed",
            document_id=str(document_id),
            error=str(exc),
        )
        try:
            raise self.retry(exc=exc, countdown=5)
        except self.MaxRetriesExceededError:
            _mark_event(event_id, "FAILED", str(exc))
