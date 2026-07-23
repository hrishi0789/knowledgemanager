"""app/api/routers/graph.py"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_current_user
from app.db.models.user import User
from app.schemas import (
    GraphEdgeOut,
    GraphNodeOut,
    GraphOverviewResponse,
    NeighborNodeOut,
    NeighborsResponse,
)
from app.services.neo4j import neo4j_session

router = APIRouter(prefix="/graph", tags=["graph"])
log = structlog.get_logger(__name__)


@router.get("/overview", response_model=GraphOverviewResponse)
async def graph_overview(
    current_user: User = Depends(get_current_user),
) -> GraphOverviewResponse:
    """Return high-level graph statistics for the user's knowledge graph."""
    try:
        with neo4j_session() as session:
            result = session.run(
                """
                MATCH (d:Document {user_id: $uid})
                OPTIONAL MATCH (c:Concept)
                OPTIONAL MATCH (t:Technology)
                OPTIONAL MATCH ()-[r:CO_OCCURS_WITH]-()
                RETURN count(DISTINCT d) AS docs,
                       count(DISTINCT c) AS concepts,
                       count(DISTINCT t) AS techs,
                       count(DISTINCT r) AS edges
                """,
                {"uid": str(current_user.id)},
            )
            row = result.single()
            return GraphOverviewResponse(
                document_count=row["docs"],
                concept_count=row["concepts"],
                technology_count=row["techs"],
                edge_count=row["edges"],
            )
    except Exception as exc:
        log.error("Graph overview query failed", error=str(exc))
        raise HTTPException(status_code=503, detail="Graph store unavailable")


@router.get("/neighbors/{node_key}", response_model=NeighborsResponse)
async def get_neighbors(
    node_key: str,
    depth: int = Query(default=1, ge=1, le=3),
    current_user: User = Depends(get_current_user),
) -> NeighborsResponse:
    """Return a node and its neighbourhood up to *depth* hops."""
    try:
        with neo4j_session() as session:
            # Fetch center node
            center_result = session.run(
                "MATCH (n {key: $key}) RETURN n.key AS key, labels(n)[0] AS label, "
                "n.name AS name, n.pagerank AS pagerank",
                {"key": node_key},
            )
            center_row = center_result.single()
            if not center_row:
                raise HTTPException(status_code=404, detail="Node not found")

            center = GraphNodeOut(
                key=center_row["key"],
                label=center_row["label"] or "Concept",
                name=center_row["name"] or node_key,
                activation=0.0,
                pagerank=center_row.get("pagerank"),
            )

            # Fetch neighbours
            nbr_result = session.run(
                """
                MATCH (n {key: $key})-[r*1..$depth]-(v)
                WHERE NOT (v:Document OR v:Chunk)
                RETURN DISTINCT v.key AS key, labels(v)[0] AS label,
                       v.name AS name, v.pagerank AS pagerank,
                       type(last(r)) AS rtype,
                       coalesce(last(r).weight, 1.0) AS weight
                LIMIT 50
                """,
                {"key": node_key, "depth": depth},
            )
            neighbors = [
                NeighborNodeOut(
                    key=r["key"],
                    label=r["label"] or "Concept",
                    name=r["name"] or r["key"],
                    pagerank=r.get("pagerank"),
                    relationship_type=r["rtype"],
                    relationship_weight=float(r["weight"]) if r.get("weight") else None,
                )
                for r in nbr_result
                if r["key"]
            ]

            return NeighborsResponse(center=center, neighbors=neighbors)

    except HTTPException:
        raise
    except Exception as exc:
        log.error("Neighbor query failed", error=str(exc))
        raise HTTPException(status_code=503, detail="Graph store unavailable")


@router.get("/cypher-presets")
async def cypher_presets(
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Return curated preset Cypher query descriptions for the UI explorer."""
    return [
        {
            "id": "most_central",
            "label": "Most central concepts",
            "cypher": "MATCH (n:Concept) RETURN n ORDER BY n.pagerank DESC LIMIT 20",
        },
        {
            "id": "tech_cooccurrence",
            "label": "Technology co-occurrence network",
            "cypher": "MATCH (a:Technology)-[r:CO_OCCURS_WITH]->(b:Technology) RETURN a,r,b LIMIT 50",
        },
        {
            "id": "prereq_chain",
            "label": "Prerequisite learning chain",
            "cypher": "MATCH p=(a:Concept)-[:PREREQUISITE_OF*1..4]->(b:Concept) RETURN p LIMIT 20",
        },
        {
            "id": "duplicates",
            "label": "Duplicate document clusters",
            "cypher": "MATCH (a:Document)-[:DUPLICATE_OF]->(b:Document) RETURN a,b LIMIT 30",
        },
    ]
