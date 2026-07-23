"""
app/core/db.py

SQLAlchemy async engine, session factory, and FastAPI dependency.
Connection pool is bounded (free-tier managed Postgres caps connections).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

settings = get_settings()

# --------------------------------------------------------------------------- #
# Engine — created once at import time; shared across workers / event loops    #
# --------------------------------------------------------------------------- #

_engine: AsyncEngine = create_async_engine(
    settings.postgres_dsn,
    pool_size=settings.postgres_pool_size,
    max_overflow=settings.postgres_pool_overflow,
    pool_pre_ping=True,          # detect stale connections before checkout
    pool_recycle=1800,           # recycle connections every 30 min
    echo=False,                  # set True only during local debugging
    future=True,
)

_async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=_engine,
    class_=AsyncSession,
    expire_on_commit=False,      # avoids lazy-load errors after commit
    autoflush=False,
    autocommit=False,
)


def get_engine() -> AsyncEngine:
    """Return the shared async engine (use in migrations / bootstrap only)."""
    return _engine


# --------------------------------------------------------------------------- #
# FastAPI dependency                                                             #
# --------------------------------------------------------------------------- #

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an ``AsyncSession`` scoped to a single request.

    Usage::

        async def endpoint(db: AsyncSession = Depends(get_session)):
            ...
    """
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# --------------------------------------------------------------------------- #
# Celery / background task helper                                               #
# --------------------------------------------------------------------------- #

from contextlib import asynccontextmanager


@asynccontextmanager
async def session_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for use inside Celery tasks (which are not
    FastAPI request handlers and therefore cannot use ``Depends``).

    Usage::

        async with session_context() as db:
            ...
    """
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
