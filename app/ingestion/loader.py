import re
from dataclasses import dataclass, field
from pathlib import Path

HEADER_RE = re.compile(r"^([A-Z_ ]+):\s*(.+)$")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)


@dataclass
class ParsedDoc:
    doc_id: str
    title: str
    effective_date: str | None
    status: str
    body: str
    source_file: str
    supersedes: list[str] = field(default_factory=list)


def parse_file(path: Path) -> ParsedDoc:
    lines = path.read_text(encoding="utf-8").splitlines()

    # 1. Read header lines ("KEY: value") until the first line that isn't one
    meta, i = {}, 0
    while i < len(lines) and (m := HEADER_RE.match(lines[i].strip())):
        meta[m.group(1).strip()] = m.group(2).strip()
        i += 1

    # 2. Everything after the header is the body; strip hidden HTML comments
    status = meta.get("STATUS", "Unknown")
    body = HTML_COMMENT_RE.sub("", "\n".join(lines[i:])).strip()

    return ParsedDoc(
        doc_id=meta["DOCUMENT_ID"],
        title=meta.get("TITLE", path.stem),
        effective_date=meta.get("EFFECTIVE DATE"),
        status=status,
        body=body,
        source_file=path.name,
        # 3. Find "Supersedes POLICY-XXXX" inside the status line
        supersedes=re.findall(r"Supersedes\s+([A-Z0-9-]+)", status),
    )