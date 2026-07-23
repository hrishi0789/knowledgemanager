"""
app/agents/classification/state.py

Persistence helpers for the OnlineClassificationEngine:
  - load_engine: restore from classifier_state or create fresh + seed
  - save_engine: upsert to classifier_state
  - add_replay / sample_replay: manage the bounded replay buffer
"""

from __future__ import annotations

import random

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.classification.engine import CATEGORIES, OnlineClassificationEngine
from app.core.config import get_settings
from app.db.models.classification import ClassificationSample, ClassifierState
from app.db.models.replay import ReplayBufferItem

log = structlog.get_logger(__name__)
settings = get_settings()

_MODEL_KEY = "ensemble"


async def load_engine(session: AsyncSession) -> OnlineClassificationEngine:
    """
    Load the classifier from DB. If no state exists, create a fresh engine
    seeded with the bootstrap corpus so cold-start prediction is meaningful.
    """
    result = await session.execute(
        select(ClassifierState).where(ClassifierState.model_key == _MODEL_KEY)
    )
    state = result.scalar_one_or_none()

    if state is not None:
        return OnlineClassificationEngine.from_blob(
            bytes(state.model_blob), CATEGORIES
        )

    # First boot: create and seed the engine
    log.info("No classifier state found — seeding from bootstrap corpus")
    from app.agents.classification.seed import SEED_CORPUS

    engine = OnlineClassificationEngine(CATEGORIES)
    texts = [t for t, _ in SEED_CORPUS]
    labels = [l for _, l in SEED_CORPUS]
    engine.learn_incrementally(texts, labels)

    await save_engine(session, engine)
    log.info("Classifier seeded", n_samples=len(SEED_CORPUS))
    return engine


async def save_engine(
    session: AsyncSession, engine: OnlineClassificationEngine
) -> None:
    """Upsert the engine blob into classifier_state (single row)."""
    blob = engine.to_blob()
    stmt = (
        pg_insert(ClassifierState)
        .values(
            model_key=_MODEL_KEY,
            model_blob=blob,
            classes=engine.categories,
            n_updates=engine.n_updates,
        )
        .on_conflict_do_update(
            index_elements=["model_key"],
            set_={
                "model_blob": blob,
                "classes": engine.categories,
                "n_updates": engine.n_updates,
                "updated_at": func.now(),
            },
        )
    )
    await session.execute(stmt)


async def add_replay(
    session: AsyncSession, label: str, text_ref: str
) -> None:
    """
    Insert a new replay buffer item, evicting the oldest if the buffer
    is at capacity (REPLAY_MAX).
    """
    # Count current buffer size
    count_result = await session.execute(
        select(func.count()).select_from(ReplayBufferItem)
    )
    current_count: int = count_result.scalar_one()

    if current_count >= settings.replay_max:
        # Evict the oldest entry
        oldest_result = await session.execute(
            select(ReplayBufferItem.id)
            .order_by(ReplayBufferItem.created_at.asc())
            .limit(1)
        )
        oldest_id = oldest_result.scalar_one_or_none()
        if oldest_id:
            await session.execute(
                delete(ReplayBufferItem).where(ReplayBufferItem.id == oldest_id)
            )

    session.add(ReplayBufferItem(label=label, text_ref=text_ref))


async def sample_replay(
    session: AsyncSession, k: int
) -> list[tuple[str, str]]:
    """
    Sample up to *k* random (label, text) pairs from the replay buffer.
    Returns fewer than *k* items if the buffer has fewer rows.
    """
    result = await session.execute(
        select(ReplayBufferItem.label, ReplayBufferItem.text_ref)
        .order_by(func.random())
        .limit(k)
    )
    return [(row.label, row.text_ref) for row in result]
