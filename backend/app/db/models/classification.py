"""app/db/models/classification.py"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import BYTEA, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ClassificationSample(Base):
    """
    Auditable record of every (text, label) pair that has been used
    to train the online classifier — including user corrections.
    """

    __tablename__ = "classification_samples"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    text_ref: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    is_labeled_by_user: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ClassifierState(Base):
    """
    Serialised model blobs (SGD + PA combined) + metadata.
    Single active row keyed by ``model_key = 'ensemble'``.
    """

    __tablename__ = "classifier_state"

    model_key: Mapped[str] = mapped_column(
        String(50), primary_key=True
    )  # 'ensemble'
    model_blob: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    classes: Mapped[list] = mapped_column(JSONB, nullable=False)
    n_updates: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
