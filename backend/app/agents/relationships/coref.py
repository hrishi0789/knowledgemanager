"""
app/agents/relationships/coref.py

Coreference resolution using fastcoref's FCoref distilled model (CPU).
Replaces pronouns with canonical noun phrases so SVO triples are self-contained.

Failure mode (05 §6): if fastcoref fails (OOM, max-length exceeded),
fall back to the original text and log a warning — never fail the whole task.
"""

from __future__ import annotations

from functools import lru_cache

import spacy
import structlog

log = structlog.get_logger(__name__)

_MAX_TEXT_LENGTH = 8_000   # chars; fastcoref has a token limit — chunk-level is safe


@lru_cache(maxsize=1)
def _get_coref_nlp() -> spacy.language.Language:
    """
    Load spaCy pipeline with fastcoref added as a component.
    Cached per-process so model is loaded once per worker.
    """
    nlp = spacy.load(
        "en_core_web_sm",
        exclude=["ner", "textcat"],   # keep tok2vec, tagger, parser, senter
    )
    try:
        nlp.add_pipe(
            "fastcoref",
            config={
                "model_architecture": "FCoref",
                "device": "cpu",
                "enable_progress_bar": False,
            },
        )
        log.info("fastcoref pipe loaded successfully")
    except Exception as exc:
        log.warning("fastcoref not available — coref disabled", error=str(exc))
    return nlp


def resolve_coreferences(text: str) -> str:
    """
    Return the coreference-resolved version of *text*.

    Pronouns are replaced with their canonical antecedent noun phrases
    so that downstream SVO extraction produces self-contained triples.

    Falls back to the original text on any error.
    """
    if len(text) > _MAX_TEXT_LENGTH:
        # Process per chunk to stay under fastcoref's token limit
        paragraphs = text.split("\n\n")
        resolved_parts: list[str] = []
        for para in paragraphs:
            resolved_parts.append(_resolve_single(para))
        return "\n\n".join(resolved_parts)

    return _resolve_single(text)


def _resolve_single(text: str) -> str:
    """Resolve coreferences in a single text block (under the length cap)."""
    text = text.strip()
    if not text:
        return text

    nlp = _get_coref_nlp()

    if "fastcoref" not in nlp.pipe_names:
        # fastcoref not available — return original
        return text

    try:
        doc = nlp(
            text,
            component_cfg={"fastcoref": {"resolve_text": True}},
        )
        resolved: str = doc._.resolved_text
        return resolved if resolved else text
    except Exception as exc:
        log.warning(
            "Coreference resolution failed — using original text",
            error=str(exc),
        )
        return text
