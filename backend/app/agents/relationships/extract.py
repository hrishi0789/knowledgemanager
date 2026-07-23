"""
app/agents/relationships/extract.py

SVO triple extraction pipeline with DP-ERE syntactic distance filtering.

Pipeline (05 §5.3):
  1. Parse sentence with spaCy (dependency parse).
  2. Build undirected dependency graph.
  3. For each VERB token: find nsubj + dobj/pobj/attr children.
  4. Filter pair if syntactic_distance(subj_head, obj_head) > max_syntactic_distance.
  5. Assign entity types via gazetteer + spaCy NER heuristic.

Returns a list of Triple dicts for Neo4j writing.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TypedDict

import spacy
import structlog

from app.agents.relationships.parse import (
    build_dependency_graph,
    span_head_index,
    syntactic_distance,
)
from app.services.gazetteer import TECH_SLUGS, is_technology
from app.services.textnorm import normalize_unicode

log = structlog.get_logger(__name__)

_MAX_SENT_TOKENS = 200   # skip pathologically long sentences


class Triple(TypedDict):
    subject: str
    verb: str
    object: str
    subj_type: str
    obj_type: str


# Entity label assignments (05 §5.4)
_SPACY_NER_TO_LABEL: dict[str, str] = {
    "PERSON": "Person",
    "ORG": "Technology",   # assume ORG in tech context → check gazetteer
    "PRODUCT": "Technology",
    "GPE": "Project",
    "LOC": "Project",
    "WORK_OF_ART": "Concept",
    "EVENT": "Concept",
}


@lru_cache(maxsize=1)
def _get_nlp() -> spacy.language.Language:
    """Load spaCy en_core_web_sm with NER enabled for entity typing."""
    return spacy.load("en_core_web_sm")


def _assign_label(span_text: str, ner_label: str | None) -> str:
    """
    Heuristic entity type assignment (05 §5.4):
      1. Gazetteer match → Technology
      2. spaCy PERSON → Person
      3. ORG/PRODUCT + gazetteer → Technology; else → Project
      4. Default → Concept
    """
    if is_technology(span_text):
        return "Technology"

    if ner_label == "PERSON":
        return "Person"

    if ner_label in {"ORG", "PRODUCT"}:
        return "Project"

    return "Concept"


def extract_triples_from_text(
    resolved_text: str,
    max_syntactic_distance: int = 4,
) -> list[Triple]:
    """
    Extract (subject, verb, object) triples from *resolved_text* using
    spaCy dependency parsing + DP-ERE distance filtering.

    Returns at most one triple per verb per sentence (the most structurally
    direct subject-object pair).
    """
    nlp = _get_nlp()
    doc = nlp(resolved_text)
    triples: list[Triple] = []

    for sent in doc.sents:
        if len(sent) > _MAX_SENT_TOKENS:
            log.debug(
                "Skipping long sentence",
                token_count=len(sent),
            )
            continue

        G = build_dependency_graph(sent)

        # Build NER label map: token_i → NER label
        ner_map: dict[int, str] = {}
        for ent in sent.ents:
            for tok in ent:
                ner_map[tok.i] = ent.label_

        for token in sent:
            if token.pos_ not in {"VERB", "AUX"} and token.dep_ != "ROOT":
                continue

            # Find nsubj (or nsubjpass)
            subj_span = None
            for child in token.children:
                if child.dep_ in {"nsubj", "nsubjpass"}:
                    # Use noun-chunk span if available, else single token
                    for chunk in doc.noun_chunks:
                        if chunk.root == child:
                            subj_span = chunk
                            break
                    if subj_span is None:
                        subj_span = child.sent[child.i : child.i + 1]
                    break

            if subj_span is None:
                continue

            # Find dobj / pobj / attr / dative / obj
            for child in token.children:
                if child.dep_ not in {
                    "dobj", "pobj", "attr", "dative", "obj",
                }:
                    continue

                obj_span = None
                for chunk in doc.noun_chunks:
                    if chunk.root == child:
                        obj_span = chunk
                        break
                if obj_span is None:
                    obj_span = child.sent[child.i : child.i + 1]

                # DP-ERE: check syntactic distance
                subj_head = span_head_index(subj_span)
                obj_head = span_head_index(obj_span)
                dist = syntactic_distance(G, subj_head, obj_head)

                if dist > max_syntactic_distance:
                    continue

                subj_text = normalize_unicode(subj_span.text)
                obj_text = normalize_unicode(obj_span.text)
                verb_lemma = token.lemma_.lower()

                subj_ner = ner_map.get(subj_span.root.i)
                obj_ner = ner_map.get(obj_span.root.i)

                triples.append(
                    Triple(
                        subject=subj_text,
                        verb=verb_lemma,
                        object=obj_text,
                        subj_type=_assign_label(subj_text, subj_ner),
                        obj_type=_assign_label(obj_text, obj_ner),
                    )
                )

    return triples
