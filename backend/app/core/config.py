"""
app/core/config.py

Single source of configuration truth. Every module reads from this
Settings instance — no hardcoded values anywhere else in the codebase.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AnyUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- PostgreSQL -------------------------------------------------------
    postgres_dsn: str = Field(
        default="postgresql+asyncpg://pkms:changeme@localhost:5432/pkms",
        description="Async SQLAlchemy DSN for the application",
    )
    postgres_sync_dsn: str = Field(
        default="postgresql+psycopg2://pkms:changeme@localhost:5432/pkms",
        description="Sync DSN used exclusively by Alembic migration env",
    )
    postgres_pool_size: int = Field(default=5, ge=1, le=20)
    postgres_pool_overflow: int = Field(default=2, ge=0)

    # ---- Redis -----------------------------------------------------------
    redis_url: str = Field(default="redis://localhost:6379/0")

    # ---- ChromaDB --------------------------------------------------------
    chroma_path: str = Field(default="./data/chroma")

    # ---- Neo4j -----------------------------------------------------------
    neo4j_uri: str = Field(default="bolt://localhost:7687")
    neo4j_user: str = Field(default="neo4j")
    neo4j_password: str = Field(default="changeme")
    neo4j_database: str = Field(default="neo4j")
    pkms_neo4j_has_gds: bool = Field(
        default=True,
        description="True when APOC + GDS plugins are installed",
    )

    # ---- Embeddings ------------------------------------------------------
    pkms_embed_device: Literal["cpu", "cuda"] = Field(default="cpu")
    pkms_embed_batch: int = Field(default=32, ge=1, le=512)
    pkms_embed_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2"
    )

    # ---- OCR -------------------------------------------------------------
    pkms_ocr_engine: Literal["pytesseract", "easyocr"] = Field(
        default="pytesseract"
    )

    # ---- File storage ----------------------------------------------------
    pkms_data_dir: str = Field(default="./data/documents")

    # ---- JWT -------------------------------------------------------------
    jwt_secret: str = Field(default="CHANGE_THIS_TO_A_RANDOM_64_CHAR_SECRET")
    jwt_algorithm: str = Field(default="HS256")
    jwt_ttl_minutes: int = Field(default=60, ge=1)

    # ---- Outbox ----------------------------------------------------------
    outbox_sweep_seconds: int = Field(default=2, ge=1)
    outbox_batch_size: int = Field(default=100, ge=1)

    # ---- Classification --------------------------------------------------
    replay_max: int = Field(default=2000, ge=100)
    replay_mix: int = Field(default=64, ge=1)

    # ---- KG Maintenance --------------------------------------------------
    kg_maintain_seconds: int = Field(default=900, ge=60)
    kg_break_cycles: bool = Field(default=False)

    # ---- Analytics -------------------------------------------------------
    analytics_seconds: int = Field(default=1800, ge=60)
    analytics_min_cooc: int = Field(default=2, ge=1)

    # ---- Dedup -----------------------------------------------------------
    jaccard_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    shingle_k: int = Field(default=3, ge=1)
    num_perm: int = Field(default=128, ge=64)
    dedup_bands: int = Field(default=16, ge=2)

    # ---- Upload ----------------------------------------------------------
    max_upload_mb: int = Field(default=50, ge=1)

    # ---- Celery ----------------------------------------------------------
    celery_worker_concurrency: int = Field(default=4, ge=1)
    celery_classifier_concurrency: int = Field(default=1, ge=1)

    # ---- Derived helpers -------------------------------------------------
    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def data_dir(self) -> Path:
        p = Path(self.pkms_data_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def chroma_dir(self) -> Path:
        p = Path(self.chroma_path)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @field_validator("jwt_secret")
    @classmethod
    def _jwt_secret_strength(cls, v: str) -> str:
        if len(v) < 32:  # noqa: PLR2004
            raise ValueError(
                "JWT_SECRET must be at least 32 characters for HS256 security"
            )
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached singleton Settings — import this everywhere."""
    return Settings()
