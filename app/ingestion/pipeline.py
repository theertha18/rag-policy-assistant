import logging
from pathlib import Path

from app.guardrails.injection import detect_injection
from app.ingestion.chunker import Chunk, chunk_document
from app.ingestion.loader import parse_file
from app.ingestion.versioning import resolve_currency

log = logging.getLogger("ingestion")


def quarantine_injected(chunks: list[Chunk]) -> tuple[list[Chunk], list[Chunk]]:
    """Split chunks into (clean, quarantined). Quarantined chunks look like instructions to an AI
    and are never stored, so they can never be retrieved and shown to the model."""
    clean, quarantined = [], []
    for chunk in chunks:
        hits = detect_injection(chunk.text)
        if hits:
            quarantined.append(chunk)
            log.warning(
                "chunk_quarantined doc_id=%s section=%s patterns=%s",
                chunk.metadata["doc_id"], chunk.metadata["section"], hits,
            )
        else:
            clean.append(chunk)
    return clean, quarantined


def ingest_directory(data_dir: str, tenant_id: str, embedder, store) -> int:
    """Load every .txt file, chunk it, quarantine suspicious chunks, embed and store the rest.
    Returns the number of chunks stored."""
    docs = [parse_file(p) for p in sorted(Path(data_dir).glob("*.txt"))]
    currency = resolve_currency(docs)
    chunks = [c for d in docs for c in chunk_document(d, tenant_id, currency[d.doc_id])]

    chunks, quarantined = quarantine_injected(chunks)
    if quarantined:
        log.warning("ingestion_quarantine count=%d", len(quarantined))
    if not chunks:
        return 0

    dense, sparse = embedder.embed_documents([c.text for c in chunks])
    store.upsert(chunks, dense, sparse)
    return len(chunks)