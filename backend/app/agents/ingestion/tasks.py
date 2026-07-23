"""
app/agents/ingestion/tasks.py

Three Celery tasks implementing the ingestion pipeline (03):
  1. ingest_document  — detect type, extract text, emit text_ready
  2. chunk_document   — normalize, chunk, embed, index, emit chunked
  3. purge_document   — delete vectors from Chroma + nodes from Neo4j
"""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from pathlib import Path

import structlog
from celery.exceptions import Reject

from app.core.config import get_settings
from app.core.logging import set_trace_id
from app.db.models.document import ExtractionStatus
from app.workers.celery_app import celery_app

log = structlog.get_logger(__name__)
settings = get_settings()


def _run(coro):
    """Run an async coroutine from a sync Celery task context."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _mark_event(event_id: str, status: str, error_msg: str | None = None) -> None:
    """Synchronously update the outbox event status via psycopg2."""
    import psycopg2

    sql = (
        "UPDATE outbox_events SET status=%s, updated_at=NOW(), "
        "error_log=%s WHERE id=%s"
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


# --------------------------------------------------------------------------- #
# Task 1: ingest_document                                                       #
# --------------------------------------------------------------------------- #


@celery_app.task(name="pkms.ingestion.ingest_document", bind=True, max_retries=5)
def ingest_document(self, payload: dict, event_id: str) -> None:
    """
    Extract raw text from the uploaded file.

    Payload: {document_id, user_id}
    """
    set_trace_id(event_id)
    document_id = uuid.UUID(payload["document_id"])

    async def _run_async() -> None:
        from app.agents.ingestion.extract import detect_kind, extract_text
        from app.core.db import session_context
        from app.db.models.document import Document, ExtractionStatus
        from app.outbox.writer import emit_event

        async with session_context() as db:
            from sqlalchemy import select

            result = await db.execute(
                select(Document).where(Document.id == document_id)
            )
            doc = result.scalar_one_or_none()
            if not doc:
                log.warning("Document not found", document_id=str(document_id))
                _mark_event(event_id, "FAILED", "Document not found")
                return

            doc.status = ExtractionStatus.EXTRACTING
            await db.flush()

            try:
                file_path = Path(settings.pkms_data_dir) / doc.source_path
                raw = file_path.read_bytes()

                kind, mime = detect_kind(raw, doc.title)
                result_obj = extract_text(raw, kind.value, mime)

                text = result_obj["text"]
                if not text.strip():
                    raise ValueError("Extracted text is empty")

                doc.status = ExtractionStatus.EXTRACTED
                doc.extracted_chars = len(text)
                doc.kind = kind
                doc.mime_type = mime

                # Store extracted text as a sidecar file to avoid DB bloat
                sidecar = file_path.with_suffix(".txt")
                sidecar.write_text(text, encoding="utf-8")

                await emit_event(
                    db,
                    "document.text_ready",
                    {"document_id": str(document_id), "user_id": str(doc.user_id)},
                )

            except Exception as exc:
                log.error(
                    "Text extraction failed",
                    document_id=str(document_id),
                    error=str(exc),
                )
                doc.status = ExtractionStatus.FAILED
                doc.error_log = str(exc)
                _mark_event(event_id, "FAILED", str(exc))
                raise

    try:
        _run(_run_async())
        _mark_event(event_id, "COMPLETED")
    except Exception as exc:
        try:
            raise self.retry(exc=exc, countdown=2 ** self.request.retries)
        except self.MaxRetriesExceededError:
            _mark_event(event_id, "FAILED", str(exc))


# --------------------------------------------------------------------------- #
# Task 2: chunk_document                                                        #
# --------------------------------------------------------------------------- #


@celery_app.task(name="pkms.ingestion.chunk_document", bind=True, max_retries=5)
def chunk_document(self, payload: dict, event_id: str) -> None:
    """
    Normalize text, semantically chunk it, extract keyphrases, embed,
    upsert to Chroma, and emit 'document.chunked'.

    Payload: {document_id, user_id}
    """
    set_trace_id(event_id)
    document_id = uuid.UUID(payload["document_id"])

    async def _run_async() -> None:
        from sqlalchemy import delete, select

        from app.agents.ingestion.chunking import chunk_text, extract_keyphrases
        from app.agents.ingestion.normalize import clean_text
        from app.core.db import session_context
        from app.db.models.chunk import Chunk
        from app.db.models.document import Document, ExtractionStatus
        from app.outbox.writer import emit_event
        from app.services.chroma import get_collection
        from app.services.embeddings import get_embedder

        async with session_context() as db:
            result = await db.execute(
                select(Document).where(Document.id == document_id)
            )
            doc = result.scalar_one_or_none()
            if not doc:
                _mark_event(event_id, "FAILED", "Document not found")
                return

            # Load extracted text from sidecar file
            file_path = Path(settings.pkms_data_dir) / doc.source_path
            sidecar = file_path.with_suffix(".txt")
            if not sidecar.exists():
                _mark_event(event_id, "FAILED", "Extracted text sidecar not found")
                return

            raw_text = sidecar.read_text(encoding="utf-8")

            # Idempotency: delete existing chunks before rechunking
            await db.execute(
                delete(Chunk).where(Chunk.document_id == document_id)
            )

            clean = clean_text(raw_text)
            if not clean.strip():
                doc.status = ExtractionStatus.INDEXED
                await emit_event(
                    db,
                    "document.chunked",
                    {"document_id": str(document_id), "user_id": str(doc.user_id)},
                )
                return

            texts = chunk_text(clean)

            embedder = get_embedder()
            vecs = embedder.encode_batched(texts, normalize=True)

            collection = get_collection()

            chunk_ids: list[str] = []
            chunk_objects: list[Chunk] = []

            for idx, (chunk_text_str, vec) in enumerate(zip(texts, vecs)):
                keyphrases = extract_keyphrases(chunk_text_str, top_k=10)
                chunk = Chunk(
                    document_id=document_id,
                    chunk_index=idx,
                    text=chunk_text_str,
                    char_count=len(chunk_text_str),
                    keyphrases=keyphrases,
                    embedded=False,
                )
                db.add(chunk)
                chunk_objects.append(chunk)

            await db.flush(chunk_objects)

            # Build Chroma upsert payload
            ids = [str(c.id) for c in chunk_objects]
            embeddings = [vecs[i] for i in range(len(chunk_objects))]
            metadatas = [
                {
                    "document_id": str(document_id),
                    "chunk_index": c.chunk_index,
                    "category": doc.category or "",
                    "user_id": str(doc.user_id),
                }
                for c in chunk_objects
            ]
            documents_preview = [c.text[:240] for c in chunk_objects]

            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=documents_preview,
            )

            # Mark all chunks as embedded
            for c in chunk_objects:
                c.embedded = True

            doc.status = ExtractionStatus.CHUNKED

            await emit_event(
                db,
                "document.chunked",
                {"document_id": str(document_id), "user_id": str(doc.user_id)},
            )

    try:
        _run(_run_async())
        _mark_event(event_id, "COMPLETED")
    except Exception as exc:
        log.error("Chunking failed", document_id=str(document_id), error=str(exc))
        try:
            raise self.retry(exc=exc, countdown=2 ** self.request.retries)
        except self.MaxRetriesExceededError:
            _mark_event(event_id, "FAILED", str(exc))


# --------------------------------------------------------------------------- #
# Task 3: purge_document                                                        #
# --------------------------------------------------------------------------- #


@celery_app.task(name="pkms.ingestion.purge_document", bind=True, max_retries=3)
def purge_document(self, payload: dict, event_id: str) -> None:
    """
    Delete all Chroma vectors and Neo4j nodes belonging to a deleted document.

    Payload: {document_id, user_id}
    Note: Postgres cascade handles the SQL rows automatically via FK ON DELETE CASCADE.
    """
    set_trace_id(event_id)
    document_id = payload["document_id"]

    try:
        # --- Chroma: delete by document_id metadata filter ---
        from app.services.chroma import get_collection

        collection = get_collection()
        # Get all chunk IDs for this document
        results = collection.get(
            where={"document_id": document_id},
            include=[],
        )
        if results["ids"]:
            collection.delete(ids=results["ids"])
            log.info(
                "Purged Chroma vectors",
                document_id=document_id,
                count=len(results["ids"]),
            )

        # --- Neo4j: delete Document node + cascade-delete orphaned Chunks ---
        from app.services.neo4j import neo4j_session

        with neo4j_session() as session:
            session.run(
                """
                MATCH (d:Document {id: $doc_id})
                OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
                OPTIONAL MATCH (c)-[cr]-()
                DELETE cr, c, d
                """,
                {"doc_id": document_id},
            )
            log.info("Purged Neo4j nodes", document_id=document_id)

        _mark_event(event_id, "COMPLETED")
    except Exception as exc:
        log.error("Purge failed", document_id=document_id, error=str(exc))
        try:
            raise self.retry(exc=exc, countdown=10)
        except self.MaxRetriesExceededError:
            _mark_event(event_id, "FAILED", str(exc))
