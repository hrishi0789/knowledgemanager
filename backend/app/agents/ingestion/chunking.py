"""
app/agents/ingestion/chunking.py

Semantic sentence chunking using cosine distance between adjacent sentence
embeddings, with a dynamic 85th-percentile threshold (03 §5.3).

Also provides keyphrase extraction via PyTextRank over spaCy.

Rules:
  - Uses the global Embedder singleton (never creates its own).
  - All chunk sizes within [min_chars, max_chars] except an unavoidably
    short trailing chunk (documented).
  - Chunking is deterministic for a fixed embedder + input.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import TypedDict

import numpy as np
import spacy
import structlog

from app.services.embeddings import get_embedder

log = structlog.get_logger(__name__)

# --------------------------------------------------------------------------- #
# Abbreviation guard list (03 §5.3)                                            #
# --------------------------------------------------------------------------- #

_ABBREVIATIONS: frozenset[str] = frozenset({
    "e.g", "i.e", "etc", "Dr", "Mr", "Mrs", "Ms",
    "vs", "Fig", "Eq", "No", "Inc", "Ltd", "U.S", "Ph.D",
    "St", "Dept", "Univ", "Corp", "Co", "Prof", "Rev",
    "Jan", "Feb", "Mar", "Apr", "Jun", "Jul", "Aug",
    "Sep", "Oct", "Nov", "Dec", "Mon", "Tue", "Wed",
    "Thu", "Fri", "Sat", "Sun",
})

# Build a regex that protects abbreviation periods
_ABBR_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(a) for a in sorted(_ABBREVIATIONS, key=len, reverse=True)) + r")\.",
    re.IGNORECASE,
)
_ABBR_PLACEHOLDER = "\x00ABR\x00"


# --------------------------------------------------------------------------- #
# spaCy NLP pipeline (loaded once per worker for keyphrase extraction)         #
# --------------------------------------------------------------------------- #


@lru_cache(maxsize=1)
def _get_nlp() -> spacy.language.Language:
    """Load spaCy en_core_web_sm with pytextrank for keyphrase extraction."""
    nlp = spacy.load("en_core_web_sm", exclude=["ner"])
    import pytextrank  # noqa: F401 — side-effect adds the pipe
    if "textrank" not in nlp.pipe_names:
        nlp.add_pipe("textrank")
    return nlp


# --------------------------------------------------------------------------- #
# Sentence splitting                                                            #
# --------------------------------------------------------------------------- #


def _split_sentences(text: str) -> list[str]:
    """
    Split *text* into sentences while protecting abbreviation periods.

    Strategy:
      1. Replace abbreviation periods with a placeholder.
      2. Split on sentence-final patterns (. ! ? followed by space + capital).
      3. Restore abbreviation periods.
    """
    # Protect abbreviations
    protected = _ABBR_PATTERN.sub(lambda m: m.group(1) + _ABBR_PLACEHOLDER, text)

    # Split on sentence boundaries: period/exclamation/question + space + uppercase
    sentences_raw = re.split(r"(?<=[.!?])\s+(?=[A-Z\"])", protected)

    # Restore placeholders
    sentences = [s.replace(_ABBR_PLACEHOLDER, ".") for s in sentences_raw]

    # Filter empty strings
    return [s.strip() for s in sentences if s.strip()]


# --------------------------------------------------------------------------- #
# Semantic chunking                                                             #
# --------------------------------------------------------------------------- #


def chunk_text(
    clean: str,
    percentile: int = 85,
    min_chars: int = 100,
    max_chars: int = 1500,
) -> list[str]:
    """
    Semantic chunking via local embeddings (03 §5.3).

    Algorithm:
      1. Split into sentences (protecting abbreviations).
      2. Embed all sentences with the shared Embedder (L2-normalised).
      3. Compute cosine distance between adjacent sentences:
             D[i] = 1 - dot(E[i], E[i+1])   (L2-normalised vectors)
      4. Threshold τ = percentile(D, 85).
      5. Place a boundary after sentence i where D[i] > τ.
      6. Greedily accumulate sentences; merge short groups with neighbours;
         hard-split groups exceeding max_chars on sentence boundaries.

    Returns an ordered list of chunk strings. Deterministic for fixed embedder.
    """
    sentences = _split_sentences(clean)

    if not sentences:
        return []

    if len(sentences) == 1:
        single = sentences[0]
        # If the single sentence is too long, hard-split on word boundaries
        if len(single) <= max_chars:
            return [single]
        return _hard_split(single, max_chars)

    # Embed all sentences in bounded batches
    embedder = get_embedder()
    embeddings = np.array(
        embedder.encode_batched(sentences, normalize=True), dtype=np.float32
    )  # shape: (N, 384)

    # Cosine distance between adjacent pairs (since normalised: 1 - dot)
    n = len(sentences)
    distances = np.array(
        [1.0 - float(np.dot(embeddings[i], embeddings[i + 1]))
         for i in range(n - 1)],
        dtype=np.float32,
    )

    tau = float(np.percentile(distances, percentile))

    # Build initial groups
    groups: list[list[str]] = []
    current_group: list[str] = [sentences[0]]

    for i, dist in enumerate(distances):
        if dist > tau:
            groups.append(current_group)
            current_group = [sentences[i + 1]]
        else:
            current_group.append(sentences[i + 1])
    groups.append(current_group)

    # Enforce length constraints
    chunks: list[str] = []
    for group in groups:
        text_block = " ".join(group)
        if len(text_block) < min_chars and chunks:
            # Merge short group with the previous chunk
            chunks[-1] = chunks[-1] + " " + text_block
        elif len(text_block) > max_chars:
            # Hard-split oversized groups on sentence boundaries
            chunks.extend(_split_group_to_max(group, max_chars))
        else:
            chunks.append(text_block)

    return [c.strip() for c in chunks if c.strip()]


def _hard_split(text: str, max_chars: int) -> list[str]:
    """Split a single long string into parts ≤ max_chars on word boundaries."""
    words = text.split()
    parts: list[str] = []
    current_words: list[str] = []
    current_len = 0
    for word in words:
        if current_len + len(word) + 1 > max_chars and current_words:
            parts.append(" ".join(current_words))
            current_words = [word]
            current_len = len(word)
        else:
            current_words.append(word)
            current_len += len(word) + 1
    if current_words:
        parts.append(" ".join(current_words))
    return parts


def _split_group_to_max(sentences: list[str], max_chars: int) -> list[str]:
    """
    Split a sentence group that exceeds max_chars into sub-chunks, each
    assembled from whole sentences up to max_chars.
    """
    result: list[str] = []
    current: list[str] = []
    current_len = 0

    for sent in sentences:
        if current_len + len(sent) + 1 > max_chars and current:
            result.append(" ".join(current))
            current = [sent]
            current_len = len(sent)
        else:
            current.append(sent)
            current_len += len(sent) + 1

    if current:
        result.append(" ".join(current))

    return result


# --------------------------------------------------------------------------- #
# Keyphrase extraction                                                          #
# --------------------------------------------------------------------------- #


class Keyphrase(TypedDict):
    text: str
    rank: float
    count: int


def extract_keyphrases(text: str, top_k: int = 10) -> list[Keyphrase]:
    """
    Extract top-k keyphrases using PyTextRank over spaCy (03 §2, interface).

    Returns list of dicts: ``{"text": str, "rank": float, "count": int}``.
    """
    nlp = _get_nlp()
    try:
        doc = nlp(text[:50_000])  # cap to avoid OOM on extremely long chunks
        phrases: list[Keyphrase] = [
            Keyphrase(
                text=phrase.text,
                rank=round(float(phrase.rank), 6),
                count=phrase.count,
            )
            for phrase in doc._.phrases[:top_k]
        ]
        return phrases
    except Exception as exc:
        log.warning("Keyphrase extraction failed", error=str(exc))
        return []
