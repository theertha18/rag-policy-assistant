from pathlib import Path

from app.ingestion.loader import parse_file

for path in sorted(Path("data").glob("*.txt")):
    doc = parse_file(path)
    print(f"{doc.doc_id:16} | supersedes={doc.supersedes} | status={doc.status}")
    print(f"{'':16} | body starts: {doc.body[:50]!r}")
    print()