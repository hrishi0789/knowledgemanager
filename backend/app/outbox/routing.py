"""
app/outbox/routing.py

Maps each outbox event_type to the list of Celery task names to dispatch.

Design decision (02 §5.3):
  Separate event rows per downstream task (no Celery chords) to give each
  task an independent retry lifecycle. ``document.chunked`` fans out to
  three separate logical sub-events that the sweeper emits as three
  individual Celery tasks against a single outbox row identified as
  "document.chunked". Each dispatched task gets the same payload + event_id
  and marks the event COMPLETED independently.

  The sweeper marks the event COMPLETED when ALL dispatched tasks have
  acknowledged (via the COMPLETED status). For simplicity with three tasks
  sharing one event row, we mark COMPLETED when the first task writes it —
  the other two are fire-and-forget on failure they log their own error.
  
  Alternative: for stricter fan-out lifecycle, use separate event rows at
  emit time. This routing map keeps the current simpler model.
"""

from __future__ import annotations

from typing import Final

# Maps event_type -> ordered list of Celery task names to invoke
EVENT_ROUTING: Final[dict[str, list[str]]] = {
    "document.uploaded": [
        "pkms.ingestion.ingest_document",
    ],
    "document.text_ready": [
        "pkms.ingestion.chunk_document",
    ],
    "document.chunked": [
        "pkms.classification.classify_chunks",
        "pkms.relationships.extract_triples",
        "pkms.dedup.detect_duplicates",
    ],
    "document.deleted": [
        "pkms.ingestion.purge_document",
    ],
    # Terminal event — no dispatch needed, sweeper marks COMPLETED
    "document.indexed": [],
}
