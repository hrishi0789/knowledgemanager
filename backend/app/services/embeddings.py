"""
app/services/embeddings.py

Singleton Embedder backed by sentence-transformers/all-MiniLM-L6-v2 (384-dim).

Rules (from 00 §6.5):
  - L2-normalized on output so cosine == dot product everywhere.
  - The SAME instance is used for chunk embedding, query embedding, and
    entity-node embedding. Do not create a second instance.
  - Device and batch size are config-driven (PKMS_EMBED_DEVICE, PKMS_EMBED_BATCH).
  - CUDA is optional acceleration; CPU is the guaranteed baseline.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Final

import numpy as np
import structlog
from sentence_transformers import SentenceTransformer

from app.core.config import get_settings

log = structlog.get_logger(__name__)
settings = get_settings()

EMBEDDING_DIM: Final[int] = 384


class Embedder:
    """
    Thin wrapper around SentenceTransformer that guarantees:
      - L2-normalized outputs (cosine == dot product)
      - Configurable device / batch size
      - A consistent dim property (384)
    """

    def __init__(self, model_name: str, device: str) -> None:
        log.info(
            "Loading embedding model",
            model=model_name,
            device=device,
        )
        self._model = SentenceTransformer(model_name, device=device)
        self.model_name = model_name
        self.dim: int = EMBEDDING_DIM

    def encode(
        self,
        texts: list[str],
        batch_size: int | None = None,
        normalize: bool = True,
    ) -> list[list[float]]:
        """
        Encode a list of texts into 384-dimensional vectors.

        Parameters
        ----------
        texts:
            Non-empty list of strings to embed.
        batch_size:
            Override the default batch size from config.
        normalize:
            If True (default), L2-normalise so cosine == dot product.

        Returns
        -------
        list of 384-float lists in the same order as *texts*.
        """
        if not texts:
            return []

        bs = batch_size or settings.pkms_embed_batch
        embeddings: np.ndarray = self._model.encode(
            texts,
            batch_size=bs,
            convert_to_numpy=True,
            normalize_embeddings=normalize,
            show_progress_bar=False,
        )
        # Shape: (N, 384) → list of plain Python lists for JSON-serialisability
        return embeddings.tolist()

    def encode_one(self, text: str, normalize: bool = True) -> list[float]:
        """Convenience wrapper for a single text."""
        result = self.encode([text], batch_size=1, normalize=normalize)
        return result[0]

    def encode_batched(
        self,
        texts: list[str],
        normalize: bool = True,
    ) -> list[list[float]]:
        """
        Same as encode() but explicitly respects the config batch size,
        iterating in bounded chunks to avoid OOM on large documents.
        """
        bs = settings.pkms_embed_batch
        all_vecs: list[list[float]] = []
        for i in range(0, len(texts), bs):
            batch = texts[i : i + bs]
            all_vecs.extend(self.encode(batch, batch_size=bs, normalize=normalize))
        return all_vecs


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    """
    Return the process-wide singleton Embedder.

    The model is loaded once per process (Celery worker keeps it warm).
    All modules MUST call ``get_embedder()`` — never instantiate Embedder
    directly.
    """
    return Embedder(
        model_name=settings.pkms_embed_model,
        device=settings.pkms_embed_device,
    )
