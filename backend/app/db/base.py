"""
app/db/base.py

SQLAlchemy declarative base shared by all ORM models.
Import this (not individual models) in alembic/env.py to get
metadata populated for autogenerate.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase, MappedColumn


class Base(DeclarativeBase):
    """Project-wide declarative base."""
    pass


# Re-export so alembic env can ``from app.db.base import Base``
# after importing all model modules to populate metadata.
__all__ = ["Base"]
