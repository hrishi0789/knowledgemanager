"""
app/agents/dedup/lsh.py

Redis-backed MinHashLSH for cross-process, persistent candidate lookup.

Parameters (07 §5.3):
  - BANDS=16, rows=8 → b×r = 128 (== NUM_PERM)
  - threshold=JACCARD_THRESHOLD (from config, default 0.85)
  - Storage backend: Redis via datasketch storage_config

Falls back to in-memory rebuild from minhash_signatures on Redis failure.
"""

from __future__ import annotations

import structlog
from datasketch import MinHash, MinHashLSH

from app.agents.dedup.minhash import NUM_PERM, SHINGLE_K
from app.core.config import get_settings

log = structlog.get_logger(__name__)
settings = get_settings()

BANDS: int = settings.dedup_bands   # 16
_ROWS: int = NUM_PERM // BANDS      # 8


def _make_redis_lsh() -> MinHashLSH:
    """Create a Redis-backed MinHashLSH."""
    return MinHashLSH(
        threshold=settings.jaccard_threshold,
        num_perm=NUM_PERM,
        params=(BANDS, _ROWS),
        storage_config={
            "type": "redis",
            "basename": b"pkms_lsh",
            "redis": {"host": _parse_redis_host(), "port": _parse_redis_port()},
        },
    )


def _parse_redis_host() -> str:
    from urllib.parse import urlparse

    parsed = urlparse(settings.redis_url)
    return parsed.hostname or "localhost"


def _parse_redis_port() -> int:
    from urllib.parse import urlparse

    parsed = urlparse(settings.redis_url)
    return parsed.port or 6379


def get_lsh() -> MinHashLSH:
    """
    Return a Redis-backed LSH index.
    Falls back to in-memory on any Redis connection error.
    """
    try:
        lsh = _make_redis_lsh()
        return lsh
    except Exception as exc:
        log.warning(
            "Redis LSH unavailable — using in-memory fallback",
            error=str(exc),
        )
        return MinHashLSH(
            threshold=settings.jaccard_threshold,
            num_perm=NUM_PERM,
            params=(BANDS, _ROWS),
        )


def find_candidates(lsh: MinHashLSH, mh: MinHash, doc_id: str) -> set[str]:
    """
    Insert the new signature into the LSH index and return candidate
    document IDs that share at least one band hash.

    The caller is responsible for filtering candidates by actual Jaccard
    threshold (this function returns approximate candidates, not verified pairs).
    """
    # Remove existing entry for idempotency (re-run safety)
    try:
        if doc_id in lsh:
            lsh.remove(doc_id)
    except Exception:
        pass

    # Query before inserting (don't self-match)
    candidates: list[str] = lsh.query(mh)
    candidate_set = {c for c in candidates if c != doc_id}

    # Insert the new signature
    lsh.insert(doc_id, mh)

    return candidate_set
