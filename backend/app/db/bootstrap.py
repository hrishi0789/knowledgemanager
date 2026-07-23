"""
app/db/bootstrap.py

Idempotent startup bootstrap called by the FastAPI lifespan hook.
Order:
  1. Run Alembic migrations to head (Postgres only — must succeed for API to serve).
  2. Get-or-create the ChromaDB collection (retries with backoff).
  3. Apply Neo4j constraints + vector indexes (IF NOT EXISTS — safe to repeat).

Bootstrap failures in Chroma/Neo4j are logged and surface a DOWNSTREAM_STORE_UNAVAILABLE
error code via /admin/health; they do NOT prevent the API from starting.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog
from alembic import command
from alembic.config import Config as AlembicConfig

from app.core.config import get_settings

log = structlog.get_logger(__name__)
settings = get_settings()

# --------------------------------------------------------------------------- #
# 1. Alembic migrations                                                          #
# --------------------------------------------------------------------------- #


def _run_migrations() -> None:
    """Run ``alembic upgrade head`` synchronously (called once at startup)."""
    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", settings.postgres_sync_dsn)
    log.info("Running Alembic migrations to head")
    command.upgrade(cfg, "head")
    log.info("Alembic migrations complete")


# --------------------------------------------------------------------------- #
# 2. ChromaDB                                                                    #
# --------------------------------------------------------------------------- #


def _bootstrap_chroma(max_attempts: int = 5, backoff: float = 2.0) -> bool:
    """
    Get-or-create the ``pkms_chunks`` Chroma collection with the canonical
    HNSW config. Retries up to *max_attempts* times.
    Returns True on success, False if Chroma is unavailable.
    """
    from app.services.chroma import CHROMA_METADATA, COLLECTION_NAME, get_chroma

    for attempt in range(1, max_attempts + 1):
        try:
            client = get_chroma()
            col = client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata=CHROMA_METADATA,
            )
            log.info(
                "Chroma collection ready",
                collection=COLLECTION_NAME,
                count=col.count(),
            )
            return True
        except Exception as exc:
            log.warning(
                "Chroma bootstrap attempt failed",
                attempt=attempt,
                error=str(exc),
            )
            if attempt < max_attempts:
                time.sleep(backoff * attempt)

    log.error("Chroma bootstrap failed after all retries — running degraded")
    return False


# --------------------------------------------------------------------------- #
# 3. Neo4j constraints + vector indexes                                          #
# --------------------------------------------------------------------------- #

_NEO4J_SETUP_QUERIES: list[str] = [
    # ---- Uniqueness constraints (idempotent IF NOT EXISTS) ----
    "CREATE CONSTRAINT document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
    "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT concept_key IF NOT EXISTS FOR (n:Concept) REQUIRE n.key IS UNIQUE",
    "CREATE CONSTRAINT tech_key IF NOT EXISTS FOR (n:Technology) REQUIRE n.key IS UNIQUE",
    "CREATE CONSTRAINT project_key IF NOT EXISTS FOR (n:Project) REQUIRE n.key IS UNIQUE",
    "CREATE CONSTRAINT person_key IF NOT EXISTS FOR (n:Person) REQUIRE n.key IS UNIQUE",
    # ---- Vector indexes for GDS semantic gate (file 01 §3.3) ----
    (
        "CREATE VECTOR INDEX concept_embedding IF NOT EXISTS "
        "FOR (n:Concept) ON (n.embedding) "
        "OPTIONS { indexConfig: { `vector.dimensions`: 384, "
        "`vector.similarity_function`: 'cosine' } }"
    ),
    (
        "CREATE VECTOR INDEX tech_embedding IF NOT EXISTS "
        "FOR (n:Technology) ON (n.embedding) "
        "OPTIONS { indexConfig: { `vector.dimensions`: 384, "
        "`vector.similarity_function`: 'cosine' } }"
    ),
]


def _bootstrap_neo4j(max_attempts: int = 5, backoff: float = 3.0) -> bool:
    """Apply all Neo4j constraints and vector indexes. Idempotent."""
    for attempt in range(1, max_attempts + 1):
        try:
            from app.services.neo4j import get_driver

            driver = get_driver()
            with driver.session(database=settings.neo4j_database) as session:
                for query in _NEO4J_SETUP_QUERIES:
                    session.run(query)
            log.info("Neo4j constraints and indexes applied")
            return True
        except Exception as exc:
            log.warning(
                "Neo4j bootstrap attempt failed",
                attempt=attempt,
                error=str(exc),
            )
            if attempt < max_attempts:
                time.sleep(backoff * attempt)

    log.error("Neo4j bootstrap failed after all retries — running degraded")
    return False


# --------------------------------------------------------------------------- #
# Public entry point                                                             #
# --------------------------------------------------------------------------- #


def run_bootstrap() -> dict[str, bool]:
    """
    Called from the FastAPI lifespan.  Migrations always run synchronously;
    Chroma/Neo4j failures are non-fatal (degraded mode).
    """
    _run_migrations()
    chroma_ok = _bootstrap_chroma()
    neo4j_ok = _bootstrap_neo4j()
    return {"postgres": True, "chroma": chroma_ok, "neo4j": neo4j_ok}
