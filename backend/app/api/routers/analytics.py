from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.agents.analytics.paths import find_learning_gaps, learning_path
from app.api.dependencies import get_current_user
from app.db.models.user import User
from app.schemas import (
    LearningGapOut,
    LearningGapsResponse,
    LearningPathRequest,
    LearningPathResponse,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.post("/learning-path", response_model=LearningPathResponse)
async def get_learning_path(
    body: LearningPathRequest,
    current_user: User = Depends(get_current_user),
) -> LearningPathResponse:
    """Return the topological prerequisite chain leading to a target concept."""
    try:
        result = learning_path(body.concept_key)
        return LearningPathResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Analytics unavailable: {exc}")


@router.get("/gaps", response_model=LearningGapsResponse)
async def get_learning_gaps(
    top_n: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
) -> LearningGapsResponse:
    """Identify prerequisite concepts the user hasn't yet studied."""
    try:
        gaps = find_learning_gaps(str(current_user.id), top_n=top_n)
        return LearningGapsResponse(gaps=[LearningGapOut(**g) for g in gaps])
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Analytics unavailable: {exc}")
