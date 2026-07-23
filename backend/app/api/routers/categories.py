from __future__ import annotations

from fastapi import APIRouter, Depends

from app.agents.classification.engine import CATEGORIES
from app.api.dependencies import get_current_user
from app.db.models.user import User

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("")
async def list_categories(
    current_user: User = Depends(get_current_user),
) -> list[str]:
    """Return the fixed list of document categories."""
    return CATEGORIES
