"""app/db/models/dedup.py"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
    SmallInteger,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import BYTEA, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DuplicateCluster(Base):
    """
    Canonical group of near-duplicate documents.
    ``representative_document_id`` is the authoritative member
    (highest-degree or lexicographically smallest UUID).
    """

    __tablename__ = "duplicate_clusters"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    representative_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    member_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
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

    members: Mapped[list["DuplicateMember"]] = relationship(
        "DuplicateMember", cascade="all, delete-orphan"
    )


class DuplicateMember(Base):
    """Maps each document to its cluster with an estimated Jaccard similarity."""

    __tablename__ = "duplicate_members"

    __table_args__ = (
        PrimaryKeyConstraint("cluster_id", "document_id"),
    )

    cluster_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("duplicate_clusters.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    jaccard_est: Mapped[float] = mapped_column(Float, nullable=False)


class MinhashSignature(Base):
    """
    Persisted MinHash signature for incremental LSH queries.
    One row per document; updated on rechunk.
    """

    __tablename__ = "minhash_signatures"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    num_perm: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=128, server_default="128"
    )
    signature: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
