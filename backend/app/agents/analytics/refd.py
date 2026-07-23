"""
app/agents/analytics/refd.py

Reference Distance (RefD) computation and prerequisite edge building (09).

RefD(A,B) uses a local co-occurrence proxy instead of the classic
Wikipedia link graph (the original corpus is unavailable):

  refA = mean over c in N(A∪B) of [1 if c co-mentioned with A else 0]
  refB = mean over c in N(A∪B) of [1 if c co-mentioned with B else 0]
  RefD(A,B) = refB - refA

  If RefD(A,B) > threshold → A PREREQUISITE_OF B
  If RefD(A,B) < -threshold → B PREREQUISITE_OF A
  If |RefD| <= threshold → no edge (too symmetric / unrelated)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import structlog

from app.core.config import get_settings
from app.services.neo4j import neo4j_session

log = structlog.get_logger(__name__)
settings = get_settings()


@dataclass
class CooccurrenceStats:
    """Per-concept co-occurrence data loaded from Neo4j."""
    key: str
    neighbors: frozenset[str]   # keys of concepts that co-occur with this one


def _load_cooccurrence(min_cooc: int) -> dict[str, CooccurrenceStats]:
    """
    Load concept co-occurrence neighbourhood from Neo4j.
    Returns a dict of concept_key → CooccurrenceStats.
    """
    with neo4j_session() as session:
        result = session.run(
            """
            MATCH (c:Chunk)-[:MENTIONS]->(a:Concept)
            MATCH (c)-[:MENTIONS]->(b:Concept)
            WHERE a.key < b.key
            WITH a, b, count(DISTINCT c) AS co_count
            WHERE co_count >= $min_cooc
            RETURN a.key AS ka, b.key AS kb
            """,
            {"min_cooc": min_cooc},
        )
        pairs = [(r["ka"], r["kb"]) for r in result]

    adjacency: dict[str, set[str]] = {}
    for ka, kb in pairs:
        adjacency.setdefault(ka, set()).add(kb)
        adjacency.setdefault(kb, set()).add(ka)

    return {
        key: CooccurrenceStats(key=key, neighbors=frozenset(nbrs))
        for key, nbrs in adjacency.items()
    }


def reference_distance(
    concept_a: str,
    concept_b: str,
    cooc: dict[str, CooccurrenceStats],
) -> float:
    """
    Compute RefD(A, B) using the local co-occurrence proxy.

    Returns a float in roughly (-1, 1).
    Positive → A is a prerequisite of B.
    Negative → B is a prerequisite of A.
    Near-zero → no prerequisite relationship.
    """
    stats_a = cooc.get(concept_a)
    stats_b = cooc.get(concept_b)

    if not stats_a or not stats_b:
        return 0.0

    # Neighbourhood = union of co-mention sets for A and B
    neighborhood = stats_a.neighbors | stats_b.neighbors
    if not neighborhood:
        return 0.0

    n = len(neighborhood)
    # ref_a: fraction of neighbours that also mention A
    ref_a = sum(1 for c in neighborhood if c in stats_a.neighbors) / n
    # ref_b: fraction of neighbours that also mention B
    ref_b = sum(1 for c in neighborhood if c in stats_b.neighbors) / n

    return ref_b - ref_a   # positive → B's neighbourhood references A more → A prereq of B


def build_prerequisite_edges(
    driver,
    threshold: float = 0.05,
    min_cooc: int | None = None,
) -> int:
    """
    Full idempotent rebuild of PREREQUISITE_OF edges (09 §5.2).

    Steps:
      1. Load co-occurrence data.
      2. Compute RefD for all candidate pairs.
      3. MERGE edges exceeding threshold; avoid 2-cycles.
      4. Delete stale edges whose |RefD| dropped below threshold.

    Returns the number of edges written.
    """
    min_cooc = min_cooc or settings.analytics_min_cooc
    cooc = _load_cooccurrence(min_cooc)
    concept_keys = list(cooc.keys())

    if len(concept_keys) < 2:  # noqa: PLR2004
        return 0

    written = 0
    existing_ab: set[tuple[str, str]] = set()

    with neo4j_session() as session:
        # Load existing prerequisite edges to avoid 2-cycles
        existing_result = session.run(
            "MATCH (a:Concept)-[r:PREREQUISITE_OF]->(b:Concept) RETURN a.key AS a, b.key AS b"
        )
        existing_ab = {(r["a"], r["b"]) for r in existing_result}

        new_edges: list[tuple[str, str, float]] = []

        # Evaluate all pairs (avoid re-computing symmetric)
        processed: set[frozenset] = set()
        for ka in concept_keys:
            for kb in cooc[ka].neighbors:
                if kb not in cooc:
                    continue
                pair = frozenset([ka, kb])
                if pair in processed:
                    continue
                processed.add(pair)

                d = reference_distance(ka, kb, cooc)

                if d > threshold:
                    # ka is prerequisite of kb
                    if (kb, ka) not in existing_ab:   # avoid 2-cycle
                        new_edges.append((ka, kb, d))
                elif d < -threshold:
                    # kb is prerequisite of ka
                    if (ka, kb) not in existing_ab:
                        new_edges.append((kb, ka, -d))

        # Clear stale edges then write fresh ones (full rebuild = idempotent)
        session.run(
            "MATCH ()-[r:PREREQUISITE_OF]->() DELETE r"
        )

        for src, dst, refd in new_edges:
            session.run(
                """
                MERGE (a:Concept {key: $src})
                MERGE (b:Concept {key: $dst})
                MERGE (a)-[r:PREREQUISITE_OF]->(b)
                SET r.refd = $refd
                """,
                {"src": src, "dst": dst, "refd": refd},
            )
            written += 1

    log.info("Prerequisite edges rebuilt", count=written)
    return written
