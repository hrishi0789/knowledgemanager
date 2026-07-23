"""
app/agents/analytics/paths.py

Learning path and gap detection queries (09 §5.3-5.4).
These are read-only Neo4j queries; all write operations are in refd.py.
"""

from __future__ import annotations

from typing import TypedDict

import structlog

from app.services.neo4j import neo4j_session

log = structlog.get_logger(__name__)


class GapInfo(TypedDict):
    concept_key: str
    concept_name: str
    dependents: int
    pagerank: float


def learning_path(target_concept_key: str) -> dict:
    """
    Return the topological ordering of prerequisites leading to *target*.

    Returns::

        {
            "path": ["prereq_key_1", "prereq_key_2", ..., "target_key"],
            "has_cycle": bool
        }

    If a cycle exists (before 06 has cleaned it), returns best-effort order
    with ``has_cycle=True``.
    """
    with neo4j_session() as session:
        # Collect ancestor prerequisite subgraph
        result = session.run(
            """
            MATCH (p:Concept)-[:PREREQUISITE_OF*1..]->(t:Concept {key: $target})
            RETURN DISTINCT p.key AS key
            """,
            {"target": target_concept_key},
        )
        ancestor_keys = [r["key"] for r in result] + [target_concept_key]

        if len(ancestor_keys) == 1:
            return {"path": ancestor_keys, "has_cycle": False}

        # Fetch edges within the subgraph for topological sort
        edge_result = session.run(
            """
            MATCH (a:Concept)-[:PREREQUISITE_OF]->(b:Concept)
            WHERE a.key IN $keys AND b.key IN $keys
            RETURN a.key AS src, b.key AS dst
            """,
            {"keys": ancestor_keys},
        )
        edges = [(r["src"], r["dst"]) for r in edge_result]

    # Topological sort via Kahn's algorithm
    path, has_cycle = _topo_sort(ancestor_keys, edges)
    return {"path": path, "has_cycle": has_cycle}


def _topo_sort(
    nodes: list[str],
    edges: list[tuple[str, str]],
) -> tuple[list[str], bool]:
    """
    Kahn's topological sort. Returns (ordered_list, has_cycle).
    has_cycle=True if the graph contains a cycle (some nodes remain unprocessed).
    """
    from collections import defaultdict, deque

    in_degree: dict[str, int] = {n: 0 for n in nodes}
    adjacency: dict[str, list[str]] = defaultdict(list)

    for src, dst in edges:
        adjacency[src].append(dst)
        in_degree[dst] = in_degree.get(dst, 0) + 1
        in_degree.setdefault(src, 0)

    queue = deque([n for n, deg in in_degree.items() if deg == 0])
    order: list[str] = []

    while queue:
        node = queue.popleft()
        order.append(node)
        for neighbour in adjacency[node]:
            in_degree[neighbour] -= 1
            if in_degree[neighbour] == 0:
                queue.append(neighbour)

    has_cycle = len(order) < len(nodes)
    # Append any remaining nodes (cycle members) at end for best-effort
    remaining = [n for n in nodes if n not in set(order)]
    return order + remaining, has_cycle


def find_learning_gaps(user_id: str, top_n: int = 10) -> list[GapInfo]:
    """
    Identify concepts the user's documents reference that have prerequisites
    the user has NOT yet studied.

    Returns gaps ranked by (dependents DESC, pagerank DESC).
    """
    with neo4j_session() as session:
        result = session.run(
            """
            // Concepts the user's documents mention
            MATCH (d:Document {user_id: $user_id})-[:HAS_CHUNK]->
                  (c:Chunk)-[:MENTIONS]->(studied:Concept)
            WITH collect(DISTINCT studied.key) AS studied_keys

            // For each studied concept, find its direct prerequisites
            MATCH (prereq:Concept)-[:PREREQUISITE_OF]->(t:Concept)
            WHERE t.key IN studied_keys
              AND NOT prereq.key IN studied_keys    // gap: not yet studied

            // Count how many studied concepts depend on this prereq
            WITH prereq,
                 count(DISTINCT t) AS dependents,
                 prereq.pagerank AS pagerank
            RETURN prereq.key AS concept_key,
                   prereq.name AS concept_name,
                   dependents,
                   coalesce(pagerank, 0.0) AS pagerank
            ORDER BY dependents DESC, pagerank DESC
            LIMIT $top_n
            """,
            {"user_id": user_id, "top_n": top_n},
        )
        return [
            GapInfo(
                concept_key=r["concept_key"],
                concept_name=r["concept_name"] or r["concept_key"],
                dependents=r["dependents"],
                pagerank=float(r["pagerank"]),
            )
            for r in result
        ]
