import re
import uuid
from dataclasses import dataclass

from app.ingestion.loader import ParsedDoc

SECTION_RE = re.compile(r"^(\d+)\.\s+(.+)$")
NAMESPACE = uuid.UUID("6f1c1f1e-0000-4000-8000-000000000001")


@dataclass
class Chunk:
    chunk_id: str
    text: str
    metadata: dict


def _clean(lines: list[str]) -> str:
    """Join lines and collapse runs of blank lines into a single blank line."""
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def chunk_document(doc: ParsedDoc, tenant_id: str, is_current: bool) -> list[Chunk]:
    """Split a document into section chunks (prose) and row chunks (tables)."""
    lines = doc.body.splitlines()
    table = [l.strip() for l in lines if l.strip().startswith("|")]
    prose = [l for l in lines if not l.strip().startswith("|")]

    pieces: list[tuple[str, str, str]] = []  # (section, chunk_type, body)

    # 1. Prose: start a new piece at every numbered heading like "2. Equipment ..."
    section, buf = "General", []
    for line in prose:
        m = SECTION_RE.match(line.strip())
        if m:
            if _clean(buf):
                pieces.append((section, "text", _clean(buf)))
            section, buf = f"{m.group(1)}. {m.group(2)}", []
        else:
            buf.append(line)
    if _clean(buf):
        pieces.append((section, "text", _clean(buf)))

    # 2. Table: one piece per row, with the column names repeated
    if len(table) > 2:
        header = [c.strip() for c in table[0].strip("|").split("|")]
        for row in table[2:]:  # skip the header row and the |:---| separator row
            cells = [c.strip() for c in row.strip("|").split("|")]
            body = "; ".join(f"{h}: {v}" for h, v in zip(header, cells))
            pieces.append((f"Table row: {cells[0]}", "table_row", body))

    # 3. Turn pieces into chunks with a source label and metadata
    chunks = []
    for idx, (sec, ctype, body) in enumerate(pieces):
        chunks.append(Chunk(
            chunk_id=str(uuid.uuid5(NAMESPACE, f"{tenant_id}:{doc.doc_id}:{idx}")),
            text=f"[{doc.doc_id}] {doc.title} | Section: {sec}\n{body}",
            metadata={
                "tenant_id": tenant_id,
                "doc_id": doc.doc_id,
                "title": doc.title,
                "section": sec,
                "chunk_type": ctype,
                "status": doc.status,
                "effective_date": doc.effective_date,
                "is_current": is_current,
                "source_file": doc.source_file,
            },
        ))
    return chunks