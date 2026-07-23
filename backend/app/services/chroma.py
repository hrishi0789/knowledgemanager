"""
app/services/chroma.py

Singleton ChromaDB client + collection accessor.
Collection: pkms_chunks (384-dim, cosine, HNSW).

All workers import get_chroma() and get_collection() — never instantiate
directly. The collection is get_or_created idempotently at bootstrap.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Final

import chromadb
import structlog
from chromadb import Collection

from app.core.config import get_settings

log = structlog.get_logger(__name__)
settings = get_settings()

COLLECTION_NAME: Final[str] = "pkms_chunks"

# Exact HNSW config from 01 §3.2 — free-tier friendly memory footprint
CHROMA_METADATA: Final[dict] = {
    "hnsw:space": "cosine",           # cosine distance (vectors are pre-L2-normalised)
    "hnsw:construction_ef": 100,      # build-time candidate list size
    "hnsw:search_ef": 64,             # query-time candidate list size
    "hnsw:M": 16,                     # max connections per node
}


@lru_cache(maxsize=1)
def get_chroma() -> chromadb.PersistentClient:
    """
    Return the singleton PersistentClient backed by the local disk path
    from ``CHROMA_PATH``.  Safe to call from multiple threads — the
    client is created once.
    """
    path = str(settings.chroma_dir)
    log.info("Initialising ChromaDB persistent client", path=path)
    return chromadb.PersistentClient(path=path)


def get_collection() -> Collection:
    """
    Return the ``pkms_chunks`` collection.  Uses get_or_create so it is
    safe to call before bootstrap has run (e.g. in tests).
    """
    client = get_chroma()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata=CHROMA_METADATA,
    )
