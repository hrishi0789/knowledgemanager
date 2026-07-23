"""
app/agents/dedup/tasks.py

Celery task: detect_duplicates (07)

Pipeline:
  1. Exact hash pre-filter (content_sha256).
  2. Shingle → MinHash signature → persist to minhash_signatures.
  3. Redis LSH candidate lookup + Jaccard threshold.
  4. Star-contraction clustering.
  5. Persist duplicate_clusters, duplicate_members, set documents.cluster_id.
  6. Write DUPLICATE_OF edges to Neo4j.
"""

from __future__ import annotations

import asyncio
import uuid

import structlog

from app.core.config import get_settings
from app.core.logging import set_trace_id
from app.workers.celery_app import celery_app

log = structlog.get_logger(__name__)
settings = get_settings()


def _mark_event(event_id: str, status: str, error_msg: str | None = None) -> None:
    import psycopg2

    sql = (
        "UPDATE outbox_events SET status=%s, updated_at=NOW(), error_log=%s WHERE id=%s"
        if error_msg
        else "UPDATE outbox_events SET status=%s, updated_at=NOW() WHERE id=%s"
    )
    with psycopg2.connect(settings.postgres_sync_dsn) as conn:
        with conn.cursor() as cur:
            args = (status, error_msg[:2000], event_id) if error_msg else (status, event_id)
            cur.execute(sql, args)
        conn.commit()


@celery_app.task(name="pkms.dedup.detect_duplicates", bind=True, max_retries=3)
def detect_duplicates(self, payload: dict, event_id: str) -> None:
    set_trace_id(event_id)
    document_id = uuid.UUID(payload["document_id"])

    async def _run_async() -> None:
        from sqlalchemy import delete, select, update
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from app.agents.dedup.cluster import star_contraction
        from app.agents.dedup.lsh import find_candidates, get_lsh
        from app.agents.dedup.minhash import (
            NUM_PERM,
            compute_signature,
            pack_signature,
            shingle,
            unpack_signature,
        )
        from app.core.db import session_context
        from app.db.models.dedup import (
            DuplicateCluster,
            DuplicateMember,
            MinhashSignature,
        )
        from app.db.models.document import Document
        from app.services.neo4j import neo4j_session

        async with session_context() as db:
            result = await db.execute(
                select(Document).where(Document.id == document_id)
            )
            doc = result.scalar_one_or_none()
            if not doc:
                return

            # ── 1. Exact-hash pre-filter ────────────────────────────────────
            existing_exact = await db.execute(
                select(Document).where(
                    Document.content_sha256 == doc.content_sha256,
                    Document.id != document_id,
                )
            )
            exact_match = existing_exact.scalar_one_or_none()
            if exact_match:
                log.info(
                    "Exact duplicate detected via SHA-256",
                    doc_id=str(document_id),
                    match_id=str(exact_match.id),
                )
                await _assign_to_existing_cluster(
                    db, document_id, exact_match.id, jaccard_est=1.0
                )
                return

            # ── 2. Load chunk text for shingling ────────────────────────────
            from app.db.models.chunk import Chunk

            chunks_result = await db.execute(
                select(Chunk.text)
                .where(Chunk.document_id == document_id)
                .order_by(Chunk.chunk_index)
            )
            chunk_texts = [r[0] for r in chunks_result]
            full_text = " ".join(chunk_texts)

            tokens = full_text.split()
            if len(tokens) < settings.shingle_k:
                log.info(
                    "Document too short for shingling — skipping dedup",
                    document_id=str(document_id),
                )
                return

            shingles = shingle(full_text)
            mh = compute_signature(shingles, NUM_PERM)
            sig_bytes = pack_signature(mh)

            # Persist signature (upsert by PK)
            stmt = pg_insert(MinhashSignature).values(
                document_id=document_id,
                num_perm=NUM_PERM,
                signature=sig_bytes,
            ).on_conflict_do_update(
                index_elements=["document_id"],
                set_={"signature": sig_bytes, "num_perm": NUM_PERM},
            )
            await db.execute(stmt)
            await db.flush()

            # ── 3. LSH candidate lookup ─────────────────────────────────────
            lsh = get_lsh()
            candidates = find_candidates(lsh, mh, str(document_id))

            if not candidates:
                # No candidates → singleton; cluster_id stays NULL
                return

            # Verify candidates by actual Jaccard estimate
            near_dup_edges: list[tuple[str, str]] = []
            all_sig_result = await db.execute(
                select(MinhashSignature).where(
                    MinhashSignature.document_id.in_(
                        [uuid.UUID(c) for c in candidates]
                    )
                )
            )
            cand_sigs = all_sig_result.scalars().all()

            for cand_sig in cand_sigs:
                cand_mh = unpack_signature(bytes(cand_sig.signature), NUM_PERM)
                jaccard = mh.jaccard(cand_mh)
                if jaccard >= settings.jaccard_threshold:
                    near_dup_edges.append((str(document_id), str(cand_sig.document_id)))

            if not near_dup_edges:
                return

            # ── 4. Star-contraction clustering ──────────────────────────────
            labels = star_contraction(near_dup_edges)

            # Group by representative
            components: dict[str, set[str]] = {}
            for node, rep in labels.items():
                components.setdefault(rep, set()).add(node)
            # Add new doc to its component
            new_doc_str = str(document_id)
            rep = labels.get(new_doc_str, new_doc_str)
            components.setdefault(rep, set()).add(new_doc_str)

            # ── 5. Persist clusters ─────────────────────────────────────────
            for rep_str, members in components.items():
                if len(members) <= 1:
                    continue

                rep_uuid = uuid.UUID(rep_str)

                # Upsert cluster
                cluster_stmt = pg_insert(DuplicateCluster).values(
                    representative_document_id=rep_uuid,
                    member_count=len(members),
                ).on_conflict_do_update(
                    constraint="duplicate_clusters_pkey",
                    set_={"member_count": len(members)},
                ).returning(DuplicateCluster.id)

                cluster_result = await db.execute(cluster_stmt)
                cluster_id = cluster_result.scalar_one()

                # Upsert members
                for member_str in members:
                    member_uuid = uuid.UUID(member_str)
                    member_mh = mh if member_str == new_doc_str else None

                    # Estimate jaccard to representative
                    if member_str == rep_str:
                        jaccard_est = 1.0
                    elif member_mh:
                        rep_sig_result = await db.execute(
                            select(MinhashSignature).where(
                                MinhashSignature.document_id == rep_uuid
                            )
                        )
                        rep_sig = rep_sig_result.scalar_one_or_none()
                        if rep_sig:
                            rep_mh = unpack_signature(bytes(rep_sig.signature), NUM_PERM)
                            jaccard_est = float(member_mh.jaccard(rep_mh))
                        else:
                            jaccard_est = 0.85
                    else:
                        jaccard_est = 0.85

                    mem_stmt = pg_insert(DuplicateMember).values(
                        cluster_id=cluster_id,
                        document_id=member_uuid,
                        jaccard_est=jaccard_est,
                    ).on_conflict_do_update(
                        constraint="duplicate_members_pkey",
                        set_={"jaccard_est": jaccard_est},
                    )
                    await db.execute(mem_stmt)

                    # Set documents.cluster_id
                    await db.execute(
                        update(Document)
                        .where(Document.id == member_uuid)
                        .values(cluster_id=cluster_id)
                    )

            # ── 6. Neo4j DUPLICATE_OF edges ─────────────────────────────────
            with neo4j_session() as session:
                for rep_str, members in components.items():
                    for member_str in members:
                        if member_str == rep_str:
                            continue
                        session.run(
                            """
                            MERGE (m:Document {id: $member})
                            MERGE (r:Document {id: $rep})
                            MERGE (m)-[:DUPLICATE_OF]->(r)
                            """,
                            {"member": member_str, "rep": rep_str},
                        )

    try:
        asyncio.get_event_loop().run_until_complete(_run_async())
        _mark_event(event_id, "COMPLETED")
    except Exception as exc:
        log.error("Dedup failed", document_id=str(document_id), error=str(exc))
        try:
            raise self.retry(exc=exc, countdown=10)
        except self.MaxRetriesExceededError:
            _mark_event(event_id, "FAILED", str(exc))


async def _assign_to_existing_cluster(db, new_doc_id, existing_doc_id, jaccard_est: float):
    """Attach new_doc to the same cluster as existing_doc (exact hash match)."""
    from sqlalchemy import select, update
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.db.models.dedup import DuplicateCluster, DuplicateMember
    from app.db.models.document import Document

    existing_result = await db.execute(
        select(Document).where(Document.id == existing_doc_id)
    )
    existing = existing_result.scalar_one_or_none()
    if not existing or existing.cluster_id is None:
        # Create a new cluster for the pair
        cluster = DuplicateCluster(
            representative_document_id=existing_doc_id,
            member_count=2,
        )
        db.add(cluster)
        await db.flush([cluster])
        cluster_id = cluster.id
        db.add(DuplicateMember(cluster_id=cluster_id, document_id=existing_doc_id, jaccard_est=1.0))
        db.add(DuplicateMember(cluster_id=cluster_id, document_id=new_doc_id, jaccard_est=1.0))
        await db.execute(
            update(Document)
            .where(Document.id.in_([existing_doc_id, new_doc_id]))
            .values(cluster_id=cluster_id)
        )
    else:
        # Attach to existing cluster
        cluster_id = existing.cluster_id
        stmt = pg_insert(DuplicateMember).values(
            cluster_id=cluster_id,
            document_id=new_doc_id,
            jaccard_est=jaccard_est,
        ).on_conflict_do_update(
            constraint="duplicate_members_pkey",
            set_={"jaccard_est": jaccard_est},
        )
        await db.execute(stmt)
        await db.execute(
            update(DuplicateCluster)
            .where(DuplicateCluster.id == cluster_id)
            .values(member_count=DuplicateCluster.member_count + 1)
        )
        await db.execute(
            update(Document)
            .where(Document.id == new_doc_id)
            .values(cluster_id=cluster_id)
        )
