"""
app/api/dependencies.py

FastAPI dependencies: JWT authentication, DB session, current user.
"""

from __future__ import annotations

import uuid

import jwt
import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import extract_user_id
from app.db.models.user import User

log = structlog.get_logger(__name__)

_bearer = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncSession = Depends(get_session),
) -> User:
    """
    Extract and validate the JWT Bearer token; return the User ORM object.
    Raises HTTP 401 on any auth failure.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        user_id_str = extract_user_id(credentials.credentials)
        user_uuid = uuid.UUID(user_id_str)
    except (jwt.PyJWTError, ValueError) as exc:
        log.warning("JWT validation failed", error=str(exc))
        raise credentials_exception from exc

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    return user
