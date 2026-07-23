"""
app/schemas/__init__.py — All Pydantic v2 request/response schemas.

Mirrors the contract in file 10 §3.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


# ──────────────────────────────────────────────────────────────────────────── #
# Auth                                                                          #
# ──────────────────────────────────────────────────────────────────────────── #

class RegisterRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int                  # seconds


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    display_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────────────────────────────────── #
# Documents                                                                     #
# ──────────────────────────────────────────────────────────────────────────── #

class DocumentOut(BaseModel):
    id: uuid.UUID
    title: str
    kind: str
    mime_type: str
    byte_size: int
    status: str
    category: str | None = None
    category_conf: float | None = None
    cluster_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    error_log: str | None = None

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    items: list[DocumentOut]
    total: int
    page: int
    page_size: int


class DocumentStatusEvent(BaseModel):
    """Server-sent event payload for status updates."""
    document_id: str
    status: str
    category: str | None = None
    category_conf: float | None = None


# ──────────────────────────────────────────────────────────────────────────── #
# Search                                                                        #
# ──────────────────────────────────────────────────────────────────────────── #

class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2048)
    top_k: int = Field(default=10, ge=1, le=50)
    category: str | None = None


class SearchHitOut(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    score: float
    preview: str
    category: str | None = None


class SearchResponse(BaseModel):
    hits: list[SearchHitOut]
    total: int
    query: str


class GraphSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2048)
    hops: int = Field(default=3, ge=1, le=6)
    decay: float = Field(default=0.7, ge=0.01, le=1.0)
    gate_threshold: float = Field(default=0.25, ge=0.0, le=1.0)
    top_k_seeds: int = Field(default=5, ge=1, le=20)


class GraphNodeOut(BaseModel):
    key: str
    label: str
    name: str
    activation: float
    pagerank: float | None = None


class GraphEdgeOut(BaseModel):
    source: str
    target: str
    type: str
    weight: float | None = None


class GraphSearchResponse(BaseModel):
    nodes: list[GraphNodeOut]
    edges: list[GraphEdgeOut]
    seed_keys: list[str]
    degraded: bool = False


# ──────────────────────────────────────────────────────────────────────────── #
# Graph exploration                                                             #
# ──────────────────────────────────────────────────────────────────────────── #

class GraphOverviewResponse(BaseModel):
    document_count: int
    concept_count: int
    technology_count: int
    edge_count: int


class NeighborNodeOut(BaseModel):
    key: str
    label: str
    name: str
    pagerank: float | None = None
    relationship_type: str
    relationship_weight: float | None = None


class NeighborsResponse(BaseModel):
    center: GraphNodeOut
    neighbors: list[NeighborNodeOut]


# ──────────────────────────────────────────────────────────────────────────── #
# Analytics                                                                     #
# ──────────────────────────────────────────────────────────────────────────── #

class LearningPathRequest(BaseModel):
    concept_key: str


class LearningPathResponse(BaseModel):
    path: list[str]
    has_cycle: bool


class LearningGapOut(BaseModel):
    concept_key: str
    concept_name: str
    dependents: int
    pagerank: float


class LearningGapsResponse(BaseModel):
    gaps: list[LearningGapOut]


# ──────────────────────────────────────────────────────────────────────────── #
# Admin                                                                         #
# ──────────────────────────────────────────────────────────────────────────── #

class StoreHealth(BaseModel):
    postgres: bool
    chroma: bool
    neo4j: bool
    redis: bool


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "down"]
    stores: StoreHealth
    version: str


class OutboxSummary(BaseModel):
    pending: int
    processing: int
    failed: int


class EvaluationReport(BaseModel):
    hit_at_1: float
    hit_at_5: float
    hit_at_10: float
    mrr: float
    ndcg_at_10: float
    classification_f1: float | None = None
    eval_time_seconds: float


# ──────────────────────────────────────────────────────────────────────────── #
# Category correction (online learning feedback loop)                          #
# ──────────────────────────────────────────────────────────────────────────── #

class CategoryCorrectionRequest(BaseModel):
    document_id: uuid.UUID
    correct_category: str
