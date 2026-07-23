"""
app/agents/ingestion/normalize.py

Knowledge Processing step: clean and normalize raw extracted text.
Implements the steps in 03 §5.2 — idempotent transformation.
"""

from __future__ import annotations

import re

from app.services.textnorm import normalize_unicode


def clean_text(raw_text: str) -> str:
    """
    Apply knowledge processing to raw extracted text.

    Steps (03 §5.2):
      1. NFKC normalization + control-char removal (via shared textnorm).
      2. Collapse horizontal whitespace to single spaces;
         preserve paragraph breaks as ``\\n``.
      3. De-hyphenate line-break splits where both sides are alphabetic
         and the joined token is ≥4 characters.
      4. Strip repeated layout artifacts (standalone page numbers).
      5. Collapse 3+ consecutive newlines to two.

    Idempotent: ``clean_text(clean_text(x)) == clean_text(x)``
    """
    text = normalize_unicode(raw_text)

    # De-hyphenation: join words broken across lines
    # Pattern: word-end hyphen + newline + word-start → rejoin
    text = re.sub(
        r"(\b[A-Za-z]{2,})-\n([A-Za-z]{2,}\b)",
        lambda m: m.group(1) + m.group(2),
        text,
    )

    # Remove standalone page numbers (common PDF artifact): lines that
    # consist of only digits (optionally with surrounding whitespace)
    text = re.sub(r"(?m)^\s*\d{1,4}\s*$", "", text)

    # Collapse runs of blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Re-run normalize_unicode to fix any new whitespace artifacts
    return normalize_unicode(text)
