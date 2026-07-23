"""
app/api/routers/documents.py

Document management endpoints (10 §2.1–2.5):
  POST   /documents/upload
  GET    /documents
  GET    /documents/{id}
  DELETE /documents/{id}
  GET    /documents/{id}/status  (SSE stream)
  POST   /documents/{id}/correct-category
"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.core.db import get_session
from app.db.models.document import Document, DocumentKind, ExtractionStatus
from app.db.models.user import User
from app.outbox.writer import emit_event
from app.schemas import (
    CategoryCorrectionRequest,
    DocumentListResponse,
    DocumentOut,
    DocumentStatusEvent,
)

router = APIRouter(prefix="/documents", tags=["documents"])
settings = get_settings()
log = structlog.get_logger(__name__)


@router.post(
    "/upload",
    response_model=DocumentOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> DocumentOut:
    """
    Accept a file upload, persist metadata + raw file, emit ingestion event.
    File size is validated against MAX_UPLOAD_MB.
    """
    raw = await file.read()

    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {settings.max_upload_mb} MB",
        )

    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    sha256 = hashlib.sha256(raw).hexdigest()
    filename = file.filename or "untitled"

    # Create document record
    doc = Document(
        user_id=current_user.id,
        title=filename,
        kind=DocumentKind.txt,    # overridden by ingestion agent
        mime_type=file.content_type or "application/octet-stream",
        source_path="",           # set after file write below
        byte_size=len(raw),
        content_sha256=sha256,
        status=ExtractionStatus.UPLOADED,
    )
    db.add(doc)
    await db.flush([doc])

    # Persist raw file to data dir
    user_dir = settings.data_dir / str(current_user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    file_path = user_dir / f"{doc.id}_{filename}"
    file_path.write_bytes(raw)

    # Store relative path (relative to pkms_data_dir)
    doc.source_path = str(Path(str(current_user.id)) / f"{doc.id}_{filename}")

    # Emit outbox event — committed atomically with the document row
    await emit_event(
        db,
        "document.uploaded",
        {"document_id": str(doc.id), "user_id": str(current_user.id)},
    )

    log.info(
        "Document uploaded",
        document_id=str(doc.id),
        user_id=str(current_user.id),
        size=len(raw),
    )
    return DocumentOut.model_validate(doc)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    category: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> DocumentListResponse:
    """List the current user's documents with pagination and optional filters."""
    from sqlalchemy import func

    base_q = select(Document).where(Document.user_id == current_user.id)

    if status_filter:
        base_q = base_q.where(Document.status == status_filter)
    if category:
        base_q = base_q.where(Document.category == category)

    # Count total
    count_q = select(func.count()).select_from(base_q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    # Paginate
    offset = (page - 1) * page_size
    items_q = (
        base_q.order_by(Document.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    items = (await db.execute(items_q)).scalars().all()

    return DocumentListResponse(
        items=[DocumentOut.model_validate(d) for d in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> DocumentOut:
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == current_user.id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentOut.model_validate(doc)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> None:
    """
    Soft-delete: emit outbox event for async cleanup, then delete PG row.
    Cascade FK handles chunks/members. Chroma+Neo4j cleaned by purge_document task.
    """
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == current_user.id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    await emit_event(
        db,
        "document.deleted",
        {"document_id": str(document_id), "user_id": str(current_user.id)},
    )
    await db.delete(doc)


@router.get("/{document_id}/status")
async def stream_document_status(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """
    Server-sent events stream for document status transitions.
    Polls Postgres every 2 seconds; closes when status is INDEXED or FAILED.
    """
    import asyncio

    async def _event_gen():
        import json
        terminal = {ExtractionStatus.INDEXED, ExtractionStatus.FAILED}
        for _ in range(150):   # max 5 minutes polling
            result = await db.execute(
                select(Document).where(
                    Document.id == document_id,
                    Document.user_id == current_user.id,
                )
            )
            doc = result.scalar_one_or_none()
            if not doc:
                yield f"data: {json.dumps({'error': 'not_found'})}\n\n"
                return
            event = DocumentStatusEvent(
                document_id=str(doc.id),
                status=doc.status.value,
                category=doc.category,
                category_conf=doc.category_conf,
            )
            yield f"data: {event.model_dump_json()}\n\n"
            if doc.status in terminal:
                return
            await asyncio.sleep(2)

    return StreamingResponse(
        _event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{document_id}/correct-category", status_code=status.HTTP_200_OK)
async def correct_category(
    document_id: uuid.UUID,
    body: CategoryCorrectionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> DocumentOut:
    """
    Record a user category correction and trigger incremental learning.
    """
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == current_user.id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    from app.db.models.classification import ClassificationSample

    sample = ClassificationSample(
        document_id=document_id,
        text_ref=f"category_correction_for_{doc.title}",
        label=body.correct_category,
        is_labeled_by_user=True,
    )
    db.add(sample)

    doc.category = body.correct_category

    # Trigger reclassification with user label
    await emit_event(
        db,
        "document.chunked",   # reuse chunked event to re-trigger classification
        {"document_id": str(document_id), "user_id": str(current_user.id)},
    )

    return DocumentOut.model_validate(doc)
