from pathlib import Path

from app.ingestion.chunker import chunk_document
from app.ingestion.loader import parse_file
from app.ingestion.versioning import resolve_currency

# 3a: parse each file and show its metadata
docs = [parse_file(p) for p in sorted(Path("data").glob("*.txt"))]
for doc in docs:
    print(f"{doc.doc_id:16} | supersedes={doc.supersedes} | status={doc.status}")
    print(f"{'':16} | body starts: {doc.body[:50]!r}")
    print()

# 3b: decide which documents are current
currency = resolve_currency(docs)
print("Currency:", currency)
print()

# 3c: cut each document into chunks and show them
for doc in docs:
    for chunk in chunk_document(doc, tenant_id="acme", is_current=currency[doc.doc_id]):
        print(f"--- current={chunk.metadata['is_current']} | type={chunk.metadata['chunk_type']}")
        print(chunk.text)
        print()