"""
app/main.py

FastAPI application factory with lifespan, CORS, error handlers, and router mounting.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.logging import configure_logging, new_trace_id, set_trace_id

settings = get_settings()
configure_logging()
log = structlog.get_logger(__name__)


# --------------------------------------------------------------------------- #
# Lifespan                                                                      #
# --------------------------------------------------------------------------- #

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: run bootstrap. Shutdown: close DB engine."""
    log.info("Starting PKMS API", version="1.0.0")

    from app.db.bootstrap import run_bootstrap

    health = run_bootstrap()
    app.state.store_health = health
    log.info("Bootstrap complete", **health)

    yield

    # Graceful shutdown
    from app.core.db import get_engine
    from app.services.neo4j import get_driver

    try:
        get_driver().close()
    except Exception:
        pass
    await get_engine().dispose()
    log.info("PKMS API stopped")


# --------------------------------------------------------------------------- #
# App factory                                                                   #
# --------------------------------------------------------------------------- #

def create_app() -> FastAPI:
    app = FastAPI(
        title="Autonomous PKMS API",
        description=(
            "Non-generative personal knowledge management system. "
            "Semantic search, graph exploration, and learning analytics."
        ),
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── CORS ────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Trace ID injection middleware ────────────────────────────────────────
    @app.middleware("http")
    async def trace_middleware(request: Request, call_next):
        trace_id = request.headers.get("X-Trace-ID") or new_trace_id()
        set_trace_id(trace_id)
        response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        return response

    # ── Global error handlers ───────────────────────────────────────────────
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)},
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        log.error("Unhandled exception", exc_type=type(exc).__name__, error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )

    # ── Routers ─────────────────────────────────────────────────────────────
    from app.api.routers.admin import router as admin_router
    from app.api.routers.analytics import router as analytics_router
    from app.api.routers.auth import router as auth_router
    from app.api.routers.categories import router as categories_router
    from app.api.routers.documents import router as documents_router
    from app.api.routers.graph import router as graph_router
    from app.api.routers.search import router as search_router

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(documents_router, prefix="/api/v1")
    app.include_router(search_router, prefix="/api/v1")
    app.include_router(graph_router, prefix="/api/v1")
    app.include_router(analytics_router, prefix="/api/v1")
    app.include_router(categories_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")

    return app


app = create_app()
