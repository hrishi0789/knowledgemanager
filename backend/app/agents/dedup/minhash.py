"""
app/agents/dedup/minhash.py

MinHash signature computation and serialization for near-duplicate detection.

Parameters (07 §4):
  - NUM_PERM = 128  hash permutations
  - SHINGLE_K = 3   word shingles
  - Pack as big-endian uint64 array (128 × 8 bytes = 1024 bytes per signature)
"""

from __future__ import annotations

import struct
from typing import Final

from datasketch import MinHash

from app.core.config import get_settings
from app.services.textnorm import normalize_unicode

settings = get_settings()

NUM_PERM: Final[int] = settings.num_perm     # 128
SHINGLE_K: Final[int] = settings.shingle_k   # 3
_PACK_FMT = f">{NUM_PERM}Q"                  # big-endian uint64 array


def shingle(text: str, k: int = SHINGLE_K) -> set[str]:
    """
    Generate k-word shingles from normalized text.

    Returns an empty set for texts with fewer than k words.
    """
    normalized = normalize_unicode(text).lower()
    tokens = normalized.split()
    if len(tokens) < k:
        return set()
    return {" ".join(tokens[i : i + k]) for i in range(len(tokens) - k + 1)}


def compute_signature(shingles: set[str], num_perm: int = NUM_PERM) -> MinHash:
    """Build a MinHash signature from a set of shingle strings."""
    mh = MinHash(num_perm=num_perm)
    for s in shingles:
        mh.update(s.encode("utf-8"))
    return mh


def pack_signature(mh: MinHash) -> bytes:
    """
    Serialise MinHash hashvalues to a compact byte string
    (NUM_PERM × uint64 big-endian = 1024 bytes for NUM_PERM=128).
    """
    return struct.pack(_PACK_FMT, *mh.hashvalues)


def unpack_signature(blob: bytes, num_perm: int = NUM_PERM) -> MinHash:
    """
    Deserialise a packed byte string back to a MinHash object.
    The restored MinHash has the same hashvalues as the original,
    so jaccard() comparisons are valid.
    """
    fmt = f">{num_perm}Q"
    hashvalues = struct.unpack(fmt, blob)
    mh = MinHash(num_perm=num_perm)
    mh.hashvalues[:] = hashvalues
    return mh
