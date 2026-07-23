"""
app/agents/kg_maintenance/resolution.py

Implements all graph hygiene operations (06):
  - resolve_entities:         merge synonym entity nodes
  - derive_cooccurrence_weights: full recompute of CO_OCCURS_WITH
  - remove_orphans:           delete zero-degree entity nodes
  - detect_prerequisite_cycles: find cycles in PREREQUISITE_OF graph
  - update_pagerank:          GDS path or networkx fallback
"""

from __future__ import annotations

import structlog
from neo4j import Session

from app.core.config import get_settings
from app.services.gazetteer import resolve_alias
from app.services.textnorm import entity_key, slug

log = structlog.get_logger(__name__)
settings = get_settings()

_ENTITY_LABELS = ("Concept", "Technology", "Project", "Person")
_EMBED_LABELS = ("Concept", "Technology")
_SIMILARITY_THRESHOLD = 0.90


# --------------------------------------------------------------------------- #
# 1. Entity resolution (synonym merge)                                          #
# --------------------------------------------------------------------------- #

def resolve_entities(driver, similarity_threshold: float = _SIMILARITY_THRESHOLD) -> int:
    """
    Merge synonym entity nodes using three signals (06 §5.1):
      a) Exact slug match after alias expansion (gazetteer)
      b) Cosine similarity of entity-name embeddings >= threshold
      c) (Future: structural Jaccard of chunk-sets — omitted for V1)

    Returns the number of merge operations performed.
    """
    merged = 0

    with driver.session(database=settings.neo4j_database) as session:
        # Signal (a): alias-based exact merges per label
        for label in _ENTITY_LABELS:
            merged += _merge_by_alias(session, label)

        # Signal (b): embedding cosine similarity for Concept + Technology
        if settings.pkms_neo4j_has_gds:
            for label in _EMBED_LABELS:
                merged += _merge_by_embedding_gds(session, label, similarity_threshold)

    log.info("Entity resolution complete", merged=merged)
    return merged


def _merge_by_alias(session: Session, label: str) -> int:
    """Merge nodes whose slug maps to the same canonical alias."""
    result = session.run(
        f"MATCH (n:{label}) RETURN n.key AS key, n.name AS name"
    )
    nodes = [(r["key"], r["name"]) for r in result]

    # Group by canonical key
    canonical_groups: dict[str, list[str]] = {}
    for key, name in nodes:
        canonical = resolve_alias(name)
        canonical_key = f"{label.lower()}:{canonical}"
        canonical_groups.setdefault(canonical_key, []).append(key)

    count = 0
    for canonical_key, member_keys in canonical_groups.items():
        if len(member_keys) <= 1:
            continue
        # Keep the canonical key node; merge others into it
        for dup_key in member_keys:
            if dup_key == canonical_key:
                continue
            _merge_node_into(session, label, dup_key, canonical_key)
            count += 1

    return count


def _merge_by_embedding_gds(
    session: Session, label: str, threshold: float
) -> int:
    """Use GDS cosine similarity to find near-duplicate entity nodes."""
    try:
        # Project entity nodes into a named graph
        graph_name = f"entity_sim_{label.lower()}"
        session.run(
            f"""
            CALL gds.graph.project(
              '{graph_name}',
              '{label}',
              '*',
              {{nodeProperties: ['embedding']}}
            )
            """
        )

        # Find pairs with cosine similarity above threshold
        result = session.run(
            f"""
            CALL gds.nodeSimilarity.stream('{graph_name}', {{
              similarityMetric: 'cosine',
              similarityCutoff: {threshold},
              topK: 5
            }})
            YIELD node1, node2, similarity
            RETURN gds.util.asNode(node1).key AS k1,
                   gds.util.asNode(node2).key AS k2,
                   similarity
            """
        )
        pairs = [(r["k1"], r["k2"]) for r in result]

        # Drop in-memory graph
        session.run(f"CALL gds.graph.drop('{graph_name}', false)")

    except Exception as exc:
        log.warning("GDS similarity failed — skipping embedding-based merge", error=str(exc))
        return 0

    count = 0
    for k1, k2 in pairs:
        # Keep the node with lower key (deterministic)
        canonical = min(k1, k2)
        duplicate = max(k1, k2)
        if k1 != k2:
            _merge_node_into(session, label, duplicate, canonical)
            count += 1

    return count


def _merge_node_into(
    session: Session, label: str, dup_key: str, canonical_key: str
) -> None:
    """
    Redirect all edges from the duplicate node to the canonical node,
    then delete the duplicate. Uses MERGE to avoid duplicate edges.
    """
    try:
        # Redirect outgoing relationships
        session.run(
            f"""
            MATCH (dup:{label} {{key: $dup}})
            MATCH (can:{label} {{key: $can}})
            CALL apoc.refactor.mergeNodes([can, dup], {{
                properties: 'discard',
                mergeRels: true
            }}) YIELD node
            RETURN node
            """,
            {"dup": dup_key, "can": canonical_key},
        )
    except Exception as exc:
        log.warning(
            "APOC merge failed — skipping",
            dup=dup_key,
            canonical=canonical_key,
            error=str(exc),
        )


# --------------------------------------------------------------------------- #
# 2. CO_OCCURS_WITH weight derivation (idempotent full recompute)               #
# --------------------------------------------------------------------------- #

def derive_cooccurrence_weights(driver) -> int:
    """
    Recompute CO_OCCURS_WITH weights by counting distinct Chunk co-mentions.
    This is authoritative — replaces any per-upload increments (05 §6).
    Returns the number of relationships written.
    """
    with driver.session(database=settings.neo4j_database) as session:
        result = session.run(
            """
            MATCH (c:Chunk)-[:MENTIONS]->(t1:Technology)
            MATCH (c)-[:MENTIONS]->(t2:Technology)
            WHERE t1.key < t2.key
            WITH t1, t2, count(DISTINCT c) AS w
            MERGE (t1)-[r:CO_OCCURS_WITH]->(t2)
            SET r.weight = w
            RETURN count(r) AS updated
            """
        )
        updated = result.single()["updated"]

    log.info("CO_OCCURS_WITH weights recomputed", updated=updated)
    return updated


# --------------------------------------------------------------------------- #
# 3. Orphan removal                                                             #
# --------------------------------------------------------------------------- #

def remove_orphans(driver) -> int:
    """
    Delete entity nodes with zero degree (no edges).
    Never deletes Document or Chunk nodes (their lifecycle is managed by outbox).
    """
    with driver.session(database=settings.neo4j_database) as session:
        result = session.run(
            """
            MATCH (n)
            WHERE (n:Concept OR n:Technology OR n:Project OR n:Person)
              AND NOT (n)--()
            WITH n, count(n) AS cnt
            DELETE n
            RETURN cnt
            """
        )
        deleted = result.single()["cnt"] if result.peek() else 0

    log.info("Orphan nodes removed", count=deleted)
    return deleted


# --------------------------------------------------------------------------- #
# 4. Prerequisite cycle detection                                               #
# --------------------------------------------------------------------------- #

def detect_prerequisite_cycles(driver) -> list[list[str]]:
    """
    Detect cycles in the PREREQUISITE_OF graph (06 §5.4).
    Returns a list of cycle paths (each path is a list of concept keys).
    Report-only by default (KG_BREAK_CYCLES=false).
    """
    with driver.session(database=settings.neo4j_database) as session:
        result = session.run(
            """
            MATCH path=(c:Concept)-[:PREREQUISITE_OF*1..]->(c)
            RETURN [n IN nodes(path) | n.key] AS cycle_keys
            LIMIT 50
            """
        )
        cycles = [r["cycle_keys"] for r in result]

    if cycles:
        log.warning("Prerequisite cycles detected", count=len(cycles))

        if settings.kg_break_cycles:
            _break_cycles(driver, cycles)

    return cycles


def _break_cycles(driver, cycles: list[list[str]]) -> None:
    """Remove the weakest (lowest refd) edge in each detected cycle."""
    with driver.session(database=settings.neo4j_database) as session:
        for cycle in cycles:
            if len(cycle) < 2:  # noqa: PLR2004
                continue
            # Find the edge with the lowest refd in this cycle and delete it
            session.run(
                """
                UNWIND $keys AS k
                MATCH (a:Concept {key: k})-[r:PREREQUISITE_OF]->(b:Concept)
                WHERE b.key IN $keys
                WITH r ORDER BY r.refd ASC LIMIT 1
                DELETE r
                """,
                {"keys": cycle},
            )


# --------------------------------------------------------------------------- #
# 5. PageRank                                                                   #
# --------------------------------------------------------------------------- #

def update_pagerank(driver) -> int:
    """
    Run PageRank over entity nodes (06 §5.5).

    GDS path (canonical): project entity nodes + CO_OCCURS_WITH edges,
    run gds.pageRank.write, drop the in-memory graph.
    networkx fallback if GDS is not available.
    """
    if settings.pkms_neo4j_has_gds:
        return _pagerank_gds(driver)
    return _pagerank_networkx(driver)


def _pagerank_gds(driver) -> int:
    """GDS PageRank write — single Cypher round-trip."""
    graph_name = "pkms_pagerank"
    try:
        with driver.session(database=settings.neo4j_database) as session:
            # Project entity nodes with CO_OCCURS_WITH (weighted)
            session.run(
                f"""
                CALL gds.graph.project(
                    '{graph_name}',
                    ['Concept','Technology','Project','Person'],
                    {{
                        CO_OCCURS_WITH: {{
                            type: 'CO_OCCURS_WITH',
                            orientation: 'UNDIRECTED',
                            properties: 'weight'
                        }},
                        PREREQUISITE_OF: {{type: 'PREREQUISITE_OF', orientation: 'NATURAL'}},
                        MENTIONS: {{type: 'MENTIONS', orientation: 'REVERSE'}},
                        USES_TECH: {{type: 'USES_TECH', orientation: 'NATURAL'}}
                    }}
                )
                """
            )
            result = session.run(
                f"""
                CALL gds.pageRank.write('{graph_name}', {{
                    dampingFactor: 0.85,
                    maxIterations: 20,
                    writeProperty: 'pagerank'
                }})
                YIELD nodePropertiesWritten
                RETURN nodePropertiesWritten
                """
            )
            written = result.single()["nodePropertiesWritten"]
            session.run(f"CALL gds.graph.drop('{graph_name}', false)")

        log.info("GDS PageRank written", nodes=written)
        return written
    except Exception as exc:
        log.error("GDS PageRank failed — falling back to networkx", error=str(exc))
        try:
            with driver.session(database=settings.neo4j_database) as session:
                session.run(f"CALL gds.graph.drop('{graph_name}', false)")
        except Exception:
            pass
        return _pagerank_networkx(driver)


def _pagerank_networkx(driver) -> int:
    """networkx fallback PageRank — loads entity graph into memory."""
    import networkx as nx

    with driver.session(database=settings.neo4j_database) as session:
        # Load entity-entity edges
        result = session.run(
            """
            MATCH (a)-[r:CO_OCCURS_WITH]->(b)
            WHERE a:Concept OR a:Technology OR a:Project OR a:Person
            RETURN a.key AS src, b.key AS dst, coalesce(r.weight, 1) AS w
            """
        )
        edges = [(r["src"], r["dst"], r["w"]) for r in result]

    G = nx.DiGraph()
    for src, dst, w in edges:
        G.add_edge(src, dst, weight=float(w))

    if not G.nodes:
        return 0

    scores = nx.pagerank(G, alpha=0.85, weight="weight", max_iter=100)

    with driver.session(database=settings.neo4j_database) as session:
        for key, score in scores.items():
            session.run(
                "MATCH (n {key: $key}) SET n.pagerank = $score",
                {"key": key, "score": float(score)},
            )

    log.info("networkx PageRank written", nodes=len(scores))
    return len(scores)
