"""
app/core/security.py

JWT creation / verification (HS256) and bcrypt password hashing.
Multi-user: every token sub = user_id (UUID string).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

# --------------------------------------------------------------------------- #
# Password hashing                                                              #
# --------------------------------------------------------------------------- #

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of *plain*."""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches the stored *hashed* string."""
    return _pwd_context.verify(plain, hashed)


# --------------------------------------------------------------------------- #
# JWT                                                                           #
# --------------------------------------------------------------------------- #

_ALGORITHM = settings.jwt_algorithm
_SECRET = settings.jwt_secret


def create_access_token(user_id: UUID | str) -> str:
    """
    Create a short-lived access token (HS256).

    Payload: ``{"sub": str(user_id), "iat": ..., "exp": ...}``
    """
    now = datetime.now(tz=timezone.utc)
    expire = now + timedelta(minutes=settings.jwt_ttl_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, _SECRET, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decode and verify a JWT.  Raises ``jwt.PyJWTError`` on any failure
    (expired, invalid signature, malformed).
    """
    return jwt.decode(
        token,
        _SECRET,
        algorithms=[_ALGORITHM],
        options={"require": ["sub", "exp", "iat"]},
    )


def extract_user_id(token: str) -> str:
    """
    High-level helper used by the FastAPI dependency.
    Returns the ``sub`` claim as a string or raises ``jwt.PyJWTError``.
    """
    payload = decode_access_token(token)
    return str(payload["sub"])
