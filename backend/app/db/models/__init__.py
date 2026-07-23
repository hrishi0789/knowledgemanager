"""
app/db/models/__init__.py

Import all models so that SQLAlchemy's metadata is fully populated
before Alembic autogenerate runs.
"""

from app.db.models.activity import ActivityLog
from app.db.models.chunk import Chunk
from app.db.models.classification import ClassificationSample, ClassifierState
from app.db.models.dedup import DuplicateCluster, DuplicateMember, MinhashSignature
from app.db.models.document import Document, DocumentKind, ExtractionStatus
from app.db.models.outbox import OutboxEvent, OutboxStatus
from app.db.models.replay import ReplayBufferItem
from app.db.models.user import User

__all__ = [
    "User",
    "Document",
    "DocumentKind",
    "ExtractionStatus",
    "Chunk",
    "OutboxEvent",
    "OutboxStatus",
    "ClassificationSample",
    "ClassifierState",
    "ReplayBufferItem",
    "DuplicateCluster",
    "DuplicateMember",
    "MinhashSignature",
    "ActivityLog",
]
