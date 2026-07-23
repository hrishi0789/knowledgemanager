"""
app/agents/relationships/writer.py

Writes extracted SVO triples to Neo4j using MERGE (idempotent).

Cypher operations (05 §3):
  - Ensure Document node exists with user_id (for multi-user scoping).
  - Ensure Chunk node exists and link Document-[:HAS_CHUNK]->Chunk.
  - MERGE entity nodes with embedding on CREATE for Concept/Technology.
  - Write Chunk-[:MENTIONS]->Entity edges.
  - CO_OCCURS_WITH weights are NOT written here — they are derived
    idempotently by KG maintenance (06) from MENTIONS counts.
  - USES_TECH edges are written here for (Project)-[USES_TECH]->(Technology).
"""

from __future__ import annotations

import structlog

from app.agents.relationships.extract import Triple
from app.services.embeddings import get_embedder
from app.services.neo4j import neo4j_session
from app.services.textnorm import entity_key, normalize_unicode

log = structlog.get_logger(__name__)

# Labels that receive an embedding vector on CREATE (for search gate in 08)
_EMBED_LABELS: frozenset[str] = frozenset({"Concept", "Technology"})


def write_triples_to_neo4j(
    document_id: str,
    document_title: str,
    document_category: str | None,
    user_id: str,
    chunk_id: str,
    triples: list[Triple],
) -> None:
    """
    Persist triples to Neo4j idempotently.

    All writes use MERGE so re-running is safe. Entity embeddings
    are set only ON CREATE to avoid overwriting KG-maintenance updates.
    """
    embedder = get_embedder()

    with neo4j_session() as session:
        # Ensure Document + Chunk nodes and HAS_CHUNK edge exist
        session.run(
            """
            MERGE (d:Document {id: $doc_id})
            ON CREATE SET
                d.title      = $title,
                d.category   = $category,
                d.user_id    = $user_id
            MERGE (c:Chunk {id: $chunk_id})
            ON CREATE SET
                c.document_id = $doc_id
            MERGE (d)-[:HAS_CHUNK]->(c)
            """,
            {
                "doc_id": document_id,
                "title": document_title,
                "category": document_category or "",
                "user_id": user_id,
                "chunk_id": chunk_id,
            },
        )

        for triple in triples:
            _write_entity(
                session,
                chunk_id=chunk_id,
                entity_name=triple["subject"],
                label=triple["subj_type"],
                embedder=embedder,
            )
            _write_entity(
                session,
                chunk_id=chunk_id,
                entity_name=triple["object"],
                label=triple["obj_type"],
                embedder=embedder,
            )

            # USES_TECH edge: Project uses Technology
            if triple["subj_type"] == "Project" and triple["obj_type"] == "Technology":
                if triple["verb"] in {"use", "uses", "using", "employ", "adopt"}:
                    _write_uses_tech(
                        session,
                        project_key=entity_key(triple["subj_type"], triple["subject"]),
                        tech_key=entity_key(triple["obj_type"], triple["object"]),
                        project_name=triple["subject"],
                        tech_name=triple["object"],
                    )


def _write_entity(
    session,
    chunk_id: str,
    entity_name: str,
    label: str,
    embedder,
) -> None:
    """MERGE entity node and Chunk-[:MENTIONS]->entity edge."""
    key = entity_key(label, entity_name)
    name = normalize_unicode(entity_name)

    # Compute embedding only for Concept and Technology nodes
    embedding: list[float] | None = None
    if label in _EMBED_LABELS:
        embedding = embedder.encode_one(name)

    if embedding is not None:
        session.run(
            f"""
            MERGE (e:{label} {{key: $key}})
            ON CREATE SET
                e.name      = $name,
                e.pagerank  = 0.0,
                e.embedding = $embedding
            MERGE (c:Chunk {{id: $chunk_id}})
            MERGE (c)-[:MENTIONS]->(e)
            """,
            {"key": key, "name": name, "embedding": embedding, "chunk_id": chunk_id},
        )
    else:
        session.run(
            f"""
            MERGE (e:{label} {{key: $key}})
            ON CREATE SET
                e.name     = $name,
                e.pagerank = 0.0
            MERGE (c:Chunk {{id: $chunk_id}})
            MERGE (c)-[:MENTIONS]->(e)
            """,
            {"key": key, "name": name, "chunk_id": chunk_id},
        )


def _write_uses_tech(
    session,
    project_key: str,
    tech_key: str,
    project_name: str,
    tech_name: str,
) -> None:
    """Write (Project)-[:USES_TECH]->(Technology) edge."""
    session.run(
        """
        MERGE (p:Project {key: $pk})
        ON CREATE SET p.name = $pname, p.pagerank = 0.0
        MERGE (t:Technology {key: $tk})
        ON CREATE SET t.name = $tname, t.pagerank = 0.0
        MERGE (p)-[:USES_TECH]->(t)
        """,
        {
            "pk": project_key,
            "pname": normalize_unicode(project_name),
            "tk": tech_key,
            "tname": normalize_unicode(tech_name),
        },
    )
