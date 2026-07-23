"""
app/agents/classification/engine.py

Online classification engine using:
  - HashingVectorizer (stateless, open vocabulary, 2^18 features)
  - SGDClassifier (modified Huber → probabilities)
  - PassiveAggressiveClassifier (hinge loss, stability backstop)

Both models are stored in a single joblib blob keyed 'ensemble' to avoid
the overhead of two separate DB round-trips.

Rules (04 §5):
  - The SAME CATEGORIES list must be passed on every partial_fit call.
  - Cold-start guard: if n_updates == 0, return Uncategorized / 0.0.
  - L2 regularisation alpha=1e-4 bounds weights across concept drift.
"""

from __future__ import annotations

import io
from typing import Final

import joblib
import numpy as np
from scipy.sparse import vstack
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.linear_model import PassiveAggressiveClassifier, SGDClassifier
from sklearn.utils.class_weight import compute_sample_weight

# Canonical category list (04 §2) — index-stable, fixed for model lifetime
CATEGORIES: Final[list[str]] = [
    "Programming",
    "Artificial Intelligence",
    "College",
    "Research",
    "Finance",
    "Personal",
    "Backend Development",
    "Frontend Development",
    "Networking",
    "Databases",
]

_VECTORIZER = HashingVectorizer(
    n_features=2**18,           # 262 144 features as per spec
    alternate_sign=True,        # reduces hash collision variance
    stop_words="english",
    ngram_range=(1, 2),         # unigrams + bigrams for short-text accuracy
    norm="l2",
)


class OnlineClassificationEngine:
    """
    Manages two online classifiers that share a single vectorizer.
    Inference uses SGD (supports predict_proba via modified Huber).
    """

    def __init__(self, categories: list[str] = CATEGORIES) -> None:
        self.categories = list(categories)
        self.sgd = SGDClassifier(
            loss="modified_huber",   # supports predict_proba
            penalty="l2",
            alpha=1e-4,
            max_iter=1000,
            tol=1e-3,
            random_state=42,
            class_weight="balanced",
        )
        self.pa = PassiveAggressiveClassifier(
            C=1.0,
            loss="hinge",
            random_state=42,
        )
        self.n_updates: int = 0

    # ------------------------------------------------------------------ #
    # Inference                                                             #
    # ------------------------------------------------------------------ #

    def infer_category(self, text: str) -> dict:
        """
        Return ``{"category": str, "confidence": float}``.

        Cold-start guard: if never fitted, returns Uncategorized / 0.0
        without calling predict (which would raise NotFittedError).
        """
        if self.n_updates == 0:
            return {"category": "Uncategorized", "confidence": 0.0}

        X = _VECTORIZER.transform([text])
        category: str = str(self.sgd.predict(X)[0])
        proba: np.ndarray = self.sgd.predict_proba(X)[0]
        confidence = float(np.max(proba))
        return {"category": category, "confidence": confidence}

    # ------------------------------------------------------------------ #
    # Training                                                              #
    # ------------------------------------------------------------------ #

    def learn_incrementally(
        self,
        texts: list[str],
        labels: list[str],
        replay_texts: list[str] | None = None,
        replay_labels: list[str] | None = None,
    ) -> None:
        """
        Partial-fit both models on new samples mixed with replay samples.

        Replay mixing (04 §5.3) prevents catastrophic forgetting:
          X_all = new_samples ∪ replay_sample
          Sample weights computed as balanced class weights.
        """
        X_new = _VECTORIZER.transform(texts)
        y_new = list(labels)

        if replay_texts and replay_labels:
            X_rep = _VECTORIZER.transform(replay_texts)
            X_all = vstack([X_new, X_rep])
            y_all = y_new + list(replay_labels)
        else:
            X_all = X_new
            y_all = y_new

        classes = np.array(self.categories)

        # Per-sample balanced class weights to handle imbalance
        sample_weights = compute_sample_weight("balanced", y_all)

        self.sgd.partial_fit(
            X_all, y_all, classes=classes, sample_weight=sample_weights
        )
        self.pa.partial_fit(
            X_all, y_all, classes=classes, sample_weight=sample_weights
        )
        self.n_updates += len(y_all)

    # ------------------------------------------------------------------ #
    # Serialisation                                                         #
    # ------------------------------------------------------------------ #

    def to_blob(self) -> bytes:
        """Serialise the engine to a joblib-pickled bytes blob."""
        buf = io.BytesIO()
        payload = {
            "sgd": self.sgd,
            "pa": self.pa,
            "categories": self.categories,
            "n_updates": self.n_updates,
        }
        joblib.dump(payload, buf, compress=3)
        return buf.getvalue()

    @classmethod
    def from_blob(
        cls,
        blob: bytes,
        categories: list[str] = CATEGORIES,
    ) -> "OnlineClassificationEngine":
        """Restore an engine from a joblib blob."""
        buf = io.BytesIO(blob)
        payload = joblib.load(buf)
        engine = cls(categories=payload["categories"])
        engine.sgd = payload["sgd"]
        engine.pa = payload["pa"]
        engine.n_updates = payload["n_updates"]
        return engine
