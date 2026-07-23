"""app/api/routers/search.py"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.search.service import multihop_search, semantic_search
from app.api.dependencies import get_current_user
from app.core.db import get_session
from app.db.models.user import User
from app.schemas import (
    GraphEdgeOut,
    GraphNodeOut,
    GraphSearchRequest,
    GraphSearchResponse,
    SearchHitOut,
    SearchRequest,
    SearchResponse,
)

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def search(
    body: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> SearchResponse:
    """Semantic search over the user's document chunks."""
    hits = await semantic_search(
        query=body.query,
        user_id=str(current_user.id),
        top_k=body.top_k,
        category=body.category,
        db=db,
    )
    return SearchResponse(
        hits=[SearchHitOut(**h) for h in hits],
        total=len(hits),
        query=body.query,
    )


@router.post("/graph", response_model=GraphSearchResponse)
async def graph_search(
    body: GraphSearchRequest,
    current_user: User = Depends(get_current_user),
) -> GraphSearchResponse:
    """Multi-hop spreading activation over the knowledge graph."""
    subgraph, degraded = multihop_search(
        query=body.query,
        user_id=str(current_user.id),
        top_k_seeds=body.top_k_seeds,
        hops=body.hops,
        decay=body.decay,
        gate_threshold=body.gate_threshold,
    )
    return GraphSearchResponse(
        nodes=[GraphNodeOut(**n) for n in subgraph["nodes"]],
        edges=[GraphEdgeOut(**e) for e in subgraph["edges"]],
        seed_keys=subgraph["seed_keys"],
        degraded=degraded,
    )
