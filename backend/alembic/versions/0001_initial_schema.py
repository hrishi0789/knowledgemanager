"""
Initial migration — creates all PKMS tables in dependency order.

Migration ordering (FK-safe):
  users → documents → chunks → outbox_events → classification_samples
  → classifier_state → replay_buffer → duplicate_clusters → duplicate_members
  → minhash_signatures → activity_log
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- extensions -------------------------------------------------------
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    # ---- enums ------------------------------------------------------------
    op.execute(
        "CREATE TYPE outbox_status AS ENUM "
        "('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')"
    )
    op.execute(
        "CREATE TYPE extraction_status AS ENUM "
        "('UPLOADED', 'EXTRACTING', 'EXTRACTED', 'CHUNKED', 'INDEXED', 'FAILED')"
    )
    op.execute(
        "CREATE TYPE document_kind AS ENUM "
        "('pdf', 'docx', 'txt', 'md', 'image', 'bookmark', 'note')"
    )

    # ---- users ------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("password_hash", sa.Text, nullable=True),
        sa.Column(
            "settings",
            postgresql.JSONB,
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # ---- documents --------------------------------------------------------
    op.create_table(
        "documents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("pdf", "docx", "txt", "md", "image", "bookmark", "note",
                    name="document_kind"),
            nullable=False,
        ),
        sa.Column("mime_type", sa.String(255), nullable=False),
        sa.Column("source_path", sa.Text, nullable=False),
        sa.Column("byte_size", sa.BigInteger, nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column(
            "status",
            sa.Enum("UPLOADED", "EXTRACTING", "EXTRACTED", "CHUNKED",
                    "INDEXED", "FAILED", name="extraction_status"),
            nullable=False,
            server_default="UPLOADED",
        ),
        sa.Column("error_log", sa.Text, nullable=True),
        sa.Column("extracted_chars", sa.Integer, nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("category_conf", sa.Float, nullable=True),
        sa.Column("cluster_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("idx_documents_user_status", "documents", ["user_id", "status"])
    op.create_index("idx_documents_category", "documents", ["category"])
    op.create_index("idx_documents_sha256", "documents", ["content_sha256"])
    op.create_index("idx_documents_cluster", "documents", ["cluster_id"])

    # ---- chunks -----------------------------------------------------------
    op.create_table(
        "chunks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("char_count", sa.Integer, nullable=False),
        sa.Column(
            "keyphrases",
            postgresql.JSONB,
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "embedded",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_chunk_doc_idx"),
    )
    op.create_index("idx_chunks_document", "chunks", ["document_id"])

    # ---- outbox_events ----------------------------------------------------
    op.create_table(
        "outbox_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "PROCESSING", "COMPLETED", "FAILED",
                    name="outbox_status"),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer, nullable=False, server_default="5"),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_log", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    # Partial index on PENDING for fast sweeper queries
    op.execute(
        "CREATE INDEX idx_outbox_pending ON outbox_events (status, created_at) "
        "WHERE status = 'PENDING'"
    )

    # ---- classification_samples ------------------------------------------
    op.create_table(
        "classification_samples",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("text_ref", sa.Text, nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column(
            "is_labeled_by_user",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("idx_class_samples_label", "classification_samples", ["label"])

    # ---- classifier_state ------------------------------------------------
    op.create_table(
        "classifier_state",
        sa.Column("model_key", sa.String(50), primary_key=True),
        sa.Column("model_blob", postgresql.BYTEA, nullable=False),
        sa.Column("classes", postgresql.JSONB, nullable=False),
        sa.Column(
            "n_updates",
            sa.BigInteger,
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ---- replay_buffer ---------------------------------------------------
    op.create_table(
        "replay_buffer",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("text_ref", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("idx_replay_created", "replay_buffer", ["created_at"])

    # ---- duplicate_clusters ----------------------------------------------
    op.create_table(
        "duplicate_clusters",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "representative_document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "member_count",
            sa.Integer,
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ---- duplicate_members -----------------------------------------------
    op.create_table(
        "duplicate_members",
        sa.Column(
            "cluster_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("duplicate_clusters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("jaccard_est", sa.Float, nullable=False),
        sa.PrimaryKeyConstraint("cluster_id", "document_id"),
    )
    op.create_index("idx_dup_members_doc", "duplicate_members", ["document_id"])

    # ---- minhash_signatures ----------------------------------------------
    op.create_table(
        "minhash_signatures",
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "num_perm",
            sa.SmallInteger,
            nullable=False,
            server_default="128",
        ),
        sa.Column("signature", postgresql.BYTEA, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ---- activity_log ----------------------------------------------------
    op.create_table(
        "activity_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB,
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "idx_activity_user_time",
        "activity_log",
        ["user_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_table("activity_log")
    op.drop_table("minhash_signatures")
    op.drop_table("duplicate_members")
    op.drop_table("duplicate_clusters")
    op.drop_table("replay_buffer")
    op.drop_table("classifier_state")
    op.drop_table("classification_samples")
    op.drop_table("outbox_events")
    op.drop_table("chunks")
    op.drop_table("documents")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS document_kind")
    op.execute("DROP TYPE IF EXISTS extraction_status")
    op.execute("DROP TYPE IF EXISTS outbox_status")
