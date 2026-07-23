"""
app/agents/search/service.py

Search service implementing two modes (08):
  1. semantic_search  — embed query → Chroma ANN → hydrate from Postgres
  2. multihop_search  — spreading activation over Neo4j entity graph
                        using GDS cosine gate in a single Cypher round-trip

Called synchronously from the FastAPI request path (no Celery).
Target latency: < 500 ms on free-tier host.
"""

from __future__ import annotations

from typing import TypedDict

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.chroma import get_collection
from app.services.embeddings import get_embedder
from app.services.neo4j import neo4j_session

log = structlog.get_logger(__name__)
settings = get_settings()


# --------------------------------------------------------------------------- #
# Public types (mirror file 10 §3 Pydantic schemas)                            #
# --------------------------------------------------------------------------- #

class SearchHit(TypedDict):
    chunk_id: str
    document_id: str
    document_title: str
    score: float
    preview: str
    category: str | None


class GraphNode(TypedDict):
    key: str
    label: str
    name: str
    activation: float
    pagerank: float | None


class GraphEdge(TypedDict):
    source: str
    target: str
    type: str
    weight: float | None


class ActivatedSubgraph(TypedDict):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    seed_keys: list[str]


# --------------------------------------------------------------------------- #
# 1. Semantic search                                                             #
# --------------------------------------------------------------------------- #

async def semantic_search(
    query: str,
    user_id: str,
    top_k: int = 10,
    category: str | None = None,
    db: AsyncSession | None = None,
) -> list[SearchHit]:
    """
    Embed query → ANN over pkms_chunks → hydrate from Postgres.
    Filters by user_id (mandatory) and optionally by category.
    """
    if not query.strip():
        return []

    embedder = get_embedder()
    e_q = embedder.encode_one(query)

    collection = get_collection()
    where: dict = {"user_id": user_id}
    if category:
        where["category"] = category

    try:
        results = collection.query(
            query_embeddings=[e_q],
            n_results=top_k,
            where=where,
            include=["metadatas", "distances", "documents"],
        )
    except Exception as exc:
        log.error("Chroma query failed", error=str(exc))
        return []

    hits: list[SearchHit] = []

    if not results["ids"] or not results["ids"][0]:
        return hits

    ids = results["ids"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]
    documents = results["documents"][0]

    # Hydrate document titles from Postgres
    doc_ids = {meta["document_id"] for meta in metadatas}
    title_map: dict[str, str] = {}

    if db and doc_ids:
        from sqlalchemy import select
        from app.db.models.document import Document

        doc_result = await db.execute(
            select(Document.id, Document.title).where(
                Document.id.in_([__import__("uuid").UUID(d) for d in doc_ids])
            )
        )
        title_map = {str(row.id): row.title for row in doc_result}

    for chunk_id, meta, dist, preview in zip(ids, metadatas, distances, documents):
        score = float(1.0 - dist)   # cosine distance → similarity
        hits.append(
            SearchHit(
                chunk_id=chunk_id,
                document_id=meta["document_id"],
                document_title=title_map.get(meta["document_id"], "Unknown"),
                score=max(0.0, min(1.0, score)),
                preview=preview or "",
                category=meta.get("category") or None,
            )
        )

    return sorted(hits, key=lambda h: h["score"], reverse=True)


# --------------------------------------------------------------------------- #
# 2. Multi-hop spreading activation                                             #
# --------------------------------------------------------------------------- #

def multihop_search(
    query: str,
    user_id: str,
    top_k_seeds: int = 5,
    hops: int = 3,
    decay: float = 0.7,
    gate_threshold: float = 0.25,
) -> tuple[ActivatedSubgraph, bool]:
    """
    Query-aware spreading activation over the Neo4j entity graph.

    Returns (ActivatedSubgraph, degraded_flag).
    degraded=True if Neo4j is unreachable (caller falls back to semantic only).

    Algorithm (08 §5.2):
      1. Embed query.
      2. Seed selection: vector index query for top_k_seeds nearest entities.
      3. Single Cypher round-trip: propagate activation along edges with
         σ(v) = gds.similarity.cosine(v.embedding, $e_q) semantic gate.
      4. Return activated nodes + their edges.
    """
    if not query.strip():
        return _empty_subgraph(), False

    embedder = get_embedder()
    e_q = embedder.encode_one(query)

    try:
        with neo4j_session() as session:
            # ── Seed selection via Neo4j vector index ──────────────────────
            if settings.pkms_neo4j_has_gds:
                seed_result = session.run(
                    """
                    CALL db.index.vector.queryNodes('concept_embedding', $k, $e_q)
                    YIELD node, score
                    RETURN node.key AS key, score
                    UNION
                    CALL db.index.vector.queryNodes('tech_embedding', $k, $e_q)
                    YIELD node, score
                    RETURN node.key AS key, score
                    ORDER BY score DESC LIMIT $k
                    """,
                    {"k": top_k_seeds, "e_q": e_q},
                )
                seed_keys = [r["key"] for r in seed_result if r["key"]][:top_k_seeds]
            else:
                seed_keys = _fallback_seed_selection(session, e_q, top_k_seeds)

            if not seed_keys:
                return _empty_subgraph(), False

            # ── Spreading activation Cypher (single round-trip) ────────────
            if settings.pkms_neo4j_has_gds:
                activation_result = session.run(
                    """
                    UNWIND $seed_keys AS sk
                    MATCH (s) WHERE s.key = sk
                    CALL {
                        WITH s
                        MATCH p=(s)-[*1..$hops]-(v)
                        WHERE (v:Concept OR v:Technology OR v:Project OR v:Person)
                          AND v.embedding IS NOT NULL
                        WITH v, reduce(a=1.0, r IN relationships(p) |
                             a * $alpha * coalesce(r.weight, 1.0)) AS decayed,
                             gds.similarity.cosine(v.embedding, $e_q) AS sigma
                        WHERE sigma >= $gate
                        RETURN v, sum(decayed * sigma) AS activation
                    }
                    RETURN v.key AS key, labels(v)[0] AS label, v.name AS name,
                           activation, v.pagerank AS pagerank
                    ORDER BY activation DESC
                    LIMIT 50
                    """,
                    {
                        "seed_keys": seed_keys,
                        "hops": hops,
                        "alpha": decay,
                        "e_q": e_q,
                        "gate": gate_threshold,
                    },
                )
            else:
                activation_result = _python_spreading_activation(
                    session, seed_keys, e_q, hops, decay, gate_threshold
                )

            nodes: list[GraphNode] = []
            activated_keys: set[str] = set()

            for record in activation_result:
                key = record["key"]
                if key:
                    nodes.append(
                        GraphNode(
                            key=key,
                            label=record["label"] or "Concept",
                            name=record["name"] or key,
                            activation=float(record["activation"] or 0.0),
                            pagerank=float(record["pagerank"]) if record.get("pagerank") else None,
                        )
                    )
                    activated_keys.add(key)

            # Fetch edges between activated nodes
            edges: list[GraphEdge] = []
            if activated_keys:
                edge_result = session.run(
                    """
                    UNWIND $keys AS k
                    MATCH (a {key: k})-[r]-(b)
                    WHERE b.key IN $keys
                    RETURN a.key AS src, b.key AS dst,
                           type(r) AS rtype, coalesce(r.weight, 1.0) AS weight
                    """,
                    {"keys": list(activated_keys)},
                )
                seen_edges: set[frozenset] = set()
                for er in edge_result:
                    edge_key = frozenset([er["src"], er["dst"], er["rtype"]])
                    if edge_key not in seen_edges:
                        edges.append(
                            GraphEdge(
                                source=er["src"],
                                target=er["dst"],
                                type=er["rtype"],
                                weight=float(er["weight"]) if er.get("weight") else None,
                            )
                        )
                        seen_edges.add(edge_key)

            return (
                ActivatedSubgraph(nodes=nodes, edges=edges, seed_keys=seed_keys),
                False,
            )

    except Exception as exc:
        log.error("Spreading activation failed — degraded mode", error=str(exc))
        return _empty_subgraph(), True


def _empty_subgraph() -> ActivatedSubgraph:
    return ActivatedSubgraph(nodes=[], edges=[], seed_keys=[])


def _fallback_seed_selection(session, e_q: list[float], k: int) -> list[str]:
    """Pure Cypher seed selection (no GDS vector index)."""
    import numpy as np

    result = session.run(
        """
        MATCH (n)
        WHERE (n:Concept OR n:Technology) AND n.embedding IS NOT NULL
        RETURN n.key AS key, n.embedding AS emb
        LIMIT 500
        """
    )
    records = [(r["key"], r["emb"]) for r in result if r["emb"]]
    if not records:
        return []

    q = np.array(e_q, dtype=np.float32)
    scores = []
    for key, emb in records:
        e = np.array(emb, dtype=np.float32)
        norm = np.linalg.norm(e)
        if norm > 0:
            scores.append((float(np.dot(q, e / norm)), key))

    scores.sort(reverse=True)
    return [key for _, key in scores[:k]]


def _python_spreading_activation(
    session, seed_keys: list[str], e_q: list[float],
    hops: int, decay: float, gate_threshold: float,
) -> list[dict]:
    """Pure Python hop-by-hop fallback for GDS-less environments."""
    import numpy as np

    # Load neighbourhood of seeds up to hops depth
    result = session.run(
        """
        UNWIND $seeds AS sk
        MATCH (s {key: sk})-[*1..$hops]-(v)
        WHERE (v:Concept OR v:Technology OR v:Project OR v:Person)
        RETURN DISTINCT v.key AS key, v.name AS name,
               labels(v)[0] AS label, v.embedding AS embedding,
               v.pagerank AS pagerank
        """,
        {"seeds": seed_keys, "hops": hops},
    )
    records = [dict(r) for r in result]

    q = np.array(e_q, dtype=np.float32)
    activated = []
    for r in records:
        emb = r.get("embedding")
        if not emb:
            continue
        e = np.array(emb, dtype=np.float32)
        norm = np.linalg.norm(e)
        if norm <= 0:
            continue
        sigma = float(np.dot(q, e / norm))
        if sigma >= gate_threshold:
            r["activation"] = sigma * decay
            activated.append(r)

    activated.sort(key=lambda x: x["activation"], reverse=True)
    return activated[:50]
