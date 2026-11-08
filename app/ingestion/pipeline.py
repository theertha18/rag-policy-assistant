from pathlib import Path

from app.ingestion.chunker import chunk_document
from app.ingestion.loader import parse_file
from app.ingestion.versioning import resolve_currency


def ingest_directory(data_dir: str, tenant_id: str, embedder, store) -> int:
    """Load every .txt file, chunk it, embed it, store it. Returns the number of chunks."""
    docs = [parse_file(p) for p in sorted(Path(data_dir).glob("*.txt"))]
    currency = resolve_currency(docs)
    chunks = [c for d in docs for c in chunk_document(d, tenant_id, currency[d.doc_id])]
    dense, sparse = embedder.embed_documents([c.text for c in chunks])
    store.upsert(chunks, dense, sparse)
    return len(chunks)