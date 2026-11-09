import math
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.generation.llm_client import FakeLLM
from app.ingestion.loader import parse_file
from app.services.rag_service import RAGService


@pytest.fixture(scope="session")
def docs() -> dict:
    """The three real policy documents, parsed once, by document ID."""
    parsed = [parse_file(p) for p in sorted(Path("data").glob("*.txt"))]
    return {d.doc_id: d for d in parsed}


# ---------- Fake components ----------

def make_point(doc_id: str, section: str, text: str):
    """Looks like a Qdrant search result: an object with a .payload dict."""
    return SimpleNamespace(payload={
        "doc_id": doc_id, "title": f"Title of {doc_id}", "section": section,
        "text": text, "effective_date": "January 1, 2025", "status": "Active",
    })


EMEA_POINT = make_point(
    "IT-SPEC-2025-A", "Table row: EMEA",
    "[IT-SPEC-2025-A] Matrix | Section: Table row: EMEA\n"
    "Region: EMEA; Laptop Allowance (Max): €1,800 EUR; Monthly Mobile Stipend: €60 EUR",
)


class FakeEmbedder:
    def embed_query(self, text):
        return "dense-vector", "sparse-vector"


class FakeStore:
    """Returns fixed points and records how it was called."""
    def __init__(self, points):
        self.points = points
        self.calls = []

    def hybrid_search(self, dense_q, sparse_q, tenant_id, include_superseded, limit):
        self.calls.append({"tenant_id": tenant_id, "include_superseded": include_superseded})
        return self.points


class FakeReranker:
    """Gives each point a fixed raw score, in order."""
    def __init__(self, raw_scores):
        self.raw_scores = raw_scores

    def rerank(self, query, points, top_k):
        scored = [(p, 1 / (1 + math.exp(-s)), s) for p, s in zip(points, self.raw_scores)]
        return sorted(scored, key=lambda item: item[2], reverse=True)[:top_k]


class FailingLLM:
    """Simulates an AI timeout."""
    calls = 0

    def complete_json(self, system, user):
        raise TimeoutError("simulated LLM timeout")


GOOD_ANSWER = {"answerable": True, "answer": "The laptop allowance is €1,800 EUR.", "sources": ["S1"]}


@pytest.fixture
def make_service():
    """Build a RAGService from fakes. Returns (service, llm, store) so tests can inspect them."""
    def _make(raw_scores=(5.0,), llm_response=None, llm=None, points=None):
        llm = llm or FakeLLM(llm_response or GOOD_ANSWER)
        store = FakeStore(points or [EMEA_POINT])
        settings = SimpleNamespace(prefetch_k=20, min_rerank_score=-10.0)
        service = RAGService(FakeEmbedder(), store, FakeReranker(list(raw_scores)), llm, settings)
        return service, llm, store
    return _make