"""
app/services/neo4j.py

Singleton Neo4j driver + convenience session helpers.

Rules from 00 §5.1:
  - get_driver() returns a single cached neo4j.GraphDatabase.driver instance.
  - All modules import this function — never create their own drivers.
  - Connection pool bounded (free-tier bolt connection cap).
"""

from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from typing import Generator

import structlog
from neo4j import Driver, GraphDatabase, Session

from app.core.config import get_settings

log = structlog.get_logger(__name__)
settings = get_settings()


@lru_cache(maxsize=1)
def get_driver() -> Driver:
    """
    Return the singleton Neo4j ``Driver``.

    Connection pool is set to 10 (enough for workers + beat without
    overwhelming a free-tier Aura / self-hosted Community instance).
    """
    log.info(
        "Creating Neo4j driver",
        uri=settings.neo4j_uri,
        database=settings.neo4j_database,
    )
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
        max_connection_pool_size=10,
        connection_timeout=30,
        max_transaction_retry_time=15,
    )
    # Verify connectivity at startup (raises if Neo4j is unreachable)
    driver.verify_connectivity()
    return driver


@contextmanager
def neo4j_session(database: str | None = None) -> Generator[Session, None, None]:
    """
    Context manager yielding a Neo4j session for the configured database.

    Usage::

        with neo4j_session() as session:
            session.run("MATCH (n) RETURN count(n)")
    """
    db = database or settings.neo4j_database
    driver = get_driver()
    with driver.session(database=db) as session:
        yield session


def run_query(
    cypher: str,
    parameters: dict | None = None,
    database: str | None = None,
) -> list[dict]:
    """
    Execute a read/write Cypher query and return all records as plain
    Python dicts.  Intended for single-statement operations.
    """
    with neo4j_session(database=database) as session:
        result = session.run(cypher, parameters or {})
        return [dict(record) for record in result]


def run_query_single(
    cypher: str,
    parameters: dict | None = None,
    database: str | None = None,
) -> dict | None:
    """
    Execute a query expected to return zero or one record.
    Returns the first record as a dict, or None.
    """
    rows = run_query(cypher, parameters, database)
    return rows[0] if rows else None
