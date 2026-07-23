"""
app/services/textnorm.py

Single shared text normalization helper used by every module.
No external dependencies beyond Python stdlib + unicodedata.
"""

from __future__ import annotations

import re
import unicodedata


def normalize_unicode(s: str) -> str:
    """
    Apply NFKC normalization, collapse whitespace runs, strip control
    characters and zero-width characters.

    Idempotent: ``normalize_unicode(normalize_unicode(x)) == normalize_unicode(x)``
    """
    # NFKC: canonical decomposition then canonical composition
    s = unicodedata.normalize("NFKC", s)
    # Remove control characters (except newline \n and tab \t which we keep)
    s = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f\u200b-\u200f\ufeff]", "", s)
    # Collapse horizontal whitespace (spaces/tabs) to single space
    s = re.sub(r"[^\S\n]+", " ", s)
    # Collapse 3+ consecutive newlines to at most 2
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def slug(name: str) -> str:
    """
    Produce a stable, normalised identifier slug from an entity name.

    Steps:
      1. ``normalize_unicode``
      2. Lowercase
      3. Strip leading/trailing whitespace
      4. Replace runs of non-alphanumeric characters with ``_``
      5. Trim leading/trailing ``_``

    Examples::

        slug("K8s ") -> "k8s"
        slug("K8s") -> "k8s"        # same as above — used for synonym merging
        slug("PostgreSQL") -> "postgresql"
        slug("Docker, Inc.") -> "docker_inc"
    """
    s = normalize_unicode(name)
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


def entity_key(label: str, name: str) -> str:
    """
    Canonical entity identifier used as the Neo4j ``key`` property.

    Format: ``"{label.lower()}:{slug(name)}"``

    This is the **only** place entity keys are minted in the codebase.
    Files 05 and 06 import this function — they never re-derive it.

    Examples::

        entity_key("Technology", "Kubernetes") -> "technology:kubernetes"
        entity_key("Technology", "K8s ") -> "technology:k8s"
        # Both map to the same key — synonym merging in 06 detects this.
    """
    return f"{label.lower()}:{slug(name)}"
