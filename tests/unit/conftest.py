from pathlib import Path

import pytest

from app.ingestion.loader import parse_file


@pytest.fixture(scope="session")
def docs() -> dict:
    """The three real policy documents, parsed once, by document ID."""
    parsed = [parse_file(p) for p in sorted(Path("data").glob("*.txt"))]
    return {d.doc_id: d for d in parsed}