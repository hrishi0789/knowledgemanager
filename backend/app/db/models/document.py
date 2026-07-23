"""app/db/models/document.py"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ExtractionStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    EXTRACTING = "EXTRACTING"
    EXTRACTED = "EXTRACTED"
    CHUNKED = "CHUNKED"
    INDEXED = "INDEXED"
    FAILED = "FAILED"


class DocumentKind(str, enum.Enum):
    pdf = "pdf"
    docx = "docx"
    txt = "txt"
    md = "md"
    image = "image"
    bookmark = "bookmark"
    note = "note"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    kind: Mapped[DocumentKind] = mapped_column(
        Enum(DocumentKind, name="document_kind"), nullable=False
    )
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_sha256: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    status: Mapped[ExtractionStatus] = mapped_column(
        Enum(ExtractionStatus, name="extraction_status"),
        nullable=False,
        default=ExtractionStatus.UPLOADED,
        server_default=ExtractionStatus.UPLOADED.value,
        index=True,
    )
    error_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_chars: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    category: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )
    category_conf: Mapped[float | None] = mapped_column(Float, nullable=True)
    cluster_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="documents")  # type: ignore[name-defined]  # noqa: F821
    chunks: Mapped[list["Chunk"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Chunk", back_populates="document", cascade="all, delete-orphan",
        order_by="Chunk.chunk_index",
    )

    def __repr__(self) -> str:
        return f"<Document id={self.id} title={self.title!r} status={self.status}>"
