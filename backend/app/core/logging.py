"""
app/core/logging.py

Structured JSON logging using structlog. Injects trace_id into every
log record so errors can be correlated across the API → outbox → agent chain.
"""

from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger

# Per-request / per-task context variable holding the active trace_id.
_trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")


def get_trace_id() -> str:
    """Return the current trace id, or a fresh one if none is set."""
    tid = _trace_id_var.get()
    if not tid:
        tid = str(uuid.uuid4())
        _trace_id_var.set(tid)
    return tid


def set_trace_id(trace_id: str) -> None:
    _trace_id_var.set(trace_id)


def new_trace_id() -> str:
    tid = str(uuid.uuid4())
    _trace_id_var.set(tid)
    return tid


# ── Structlog processors ────────────────────────────────────────────────────


def _inject_trace_id(
    logger: WrappedLogger,
    method: str,
    event_dict: EventDict,
) -> EventDict:
    event_dict["trace_id"] = get_trace_id()
    return event_dict


def configure_logging(log_level: str = "INFO") -> None:
    """
    Call once at application startup. After this, use ``structlog.get_logger()``
    everywhere — it produces JSON lines in production and coloured text in dev.
    """
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        _inject_trace_id,
        structlog.processors.StackInfoRenderer(),
    ]

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Silence noisy third-party loggers
    for noisy in ("httpx", "httpcore", "asyncio", "multipart"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


# Module-level logger for use within this package
log = structlog.get_logger(__name__)
