import time
from datetime import datetime
from pathlib import Path

import pytest

from app.config import settings
from app.generation.llm_client import OpenAICompatibleClient
from app.ingestion.pipeline import ingest_directory
from app.retrieval.embeddings import Embedder
from app.retrieval.reranker import Reranker
from app.retrieval.vector_store import VectorStore
from app.services.rag_service import RAGService

from .judge import FaithfulnessJudge

PAUSE_SECONDS = 6       # spacing between cases, to stay under free-tier rate limits
EVAL_RETRIES = 3        # nobody is waiting during evaluation, so be patient with 429s


def _llm() -> OpenAICompatibleClient:
    return OpenAICompatibleClient(
        settings.llm_api_key, settings.llm_model, settings.llm_base_url, rate_limit_retries=EVAL_RETRIES
    )


@pytest.fixture(scope="session")
def rag_service():
    if not settings.llm_api_key:
        pytest.skip("LLM_API_KEY not set; evaluation needs a real model")
    embedder = Embedder(settings.dense_model, settings.sparse_model)
    store = VectorStore(settings.qdrant_url, settings.collection)
    store.ensure_collection()
    if store.count() == 0:
        ingest_directory(settings.data_dir, settings.default_tenant, embedder, store)
    return RAGService(embedder, store, Reranker(settings.rerank_model), _llm(), settings)


@pytest.fixture(scope="session")
def judge():
    return FaithfulnessJudge(_llm())


@pytest.fixture(autouse=True)
def pause_between_cases():
    yield
    time.sleep(PAUSE_SECONDS)


@pytest.fixture(scope="session")
def report():
    rows: list[dict] = []
    yield rows
    _write_report(rows)


COLUMNS = [
    ("id", "Case"), ("category", "Category"), ("status", "Status"), ("reason", "Refusal reason"),
    ("context_recall", "Context recall"), ("citation_recall", "Citation recall"),
    ("fact_recall", "Fact recall"), ("faithfulness", "Faithfulness"),
    ("source_exclusion", "Excluded sources absent"), ("refusal_correct", "Refusal correct"),
    ("latency_ms", "Latency (ms)"), ("passed", "Result"),
]


def _fmt(key: str, value) -> str:
    if value is None:
        return "–"
    if key == "passed":
        return "**PASS**" if value else "**FAIL**"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _write_report(rows: list[dict]) -> None:
    if not rows:
        return
    rows = sorted(rows, key=lambda r: r["id"])
    answered = [r for r in rows if r["faithfulness"] is not None]
    avg_faith = sum(r["faithfulness"] for r in answered) / len(answered) if answered else None
    lines = [
        "# Benchmark evaluation report",
        "",
        f"- Run: {datetime.now():%Y-%m-%d %H:%M}",
        f"- LLM: `{settings.llm_model}` · Re-ranker: `{settings.rerank_model}` · Gate 1 threshold: `{settings.min_rerank_score}`",
        f"- Result: **{sum(r['passed'] for r in rows)}/{len(rows)} cases passed**"
        + (f" · Mean faithfulness: **{avg_faith:.2f}**" if avg_faith is not None else ""),
        "",
        "| " + " | ".join(title for _, title in COLUMNS) + " |",
        "|" + "---|" * len(COLUMNS),
    ]
    lines += ["| " + " | ".join(_fmt(k, r.get(k)) for k, _ in COLUMNS) + " |" for r in rows]
    flagged = [r for r in rows if r.get("unsupported_claims")]
    if flagged:
        lines += ["", "## Unsupported claims flagged by the judge", ""]
        lines += [f"- **{r['id']}**: {'; '.join(r['unsupported_claims'])}" for r in flagged]
    failed = [r for r in rows if not r["passed"]]
    if failed:
        lines += ["", "## Failed checks", ""]
        lines += [f"- **{r['id']}**: {', '.join(r['failed_checks'])} (reason: {r.get('reason')})" for r in failed]
    Path("reports").mkdir(exist_ok=True)
    Path("reports/benchmark_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")