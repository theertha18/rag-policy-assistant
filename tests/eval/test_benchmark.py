import json
from pathlib import Path

import pytest

from app.retrieval.query_enrichment import enrich_query
from app.schemas.query import QueryRequest

from .expectations import EXPECTATIONS, EXTRA_CASES

BENCHMARK = json.loads(Path("data/benchmark_eval.json").read_text(encoding="utf-8"))
CASES = BENCHMARK + EXTRA_CASES


def _norm(text: str) -> str:
    return text.replace(",", "").lower()


@pytest.mark.eval
@pytest.mark.parametrize("case", CASES, ids=[c["eval_id"] for c in CASES])
def test_benchmark_case(case, rag_service, judge, report):
    exp = EXPECTATIONS[case["eval_id"]]
    resp = rag_service.answer(QueryRequest(query=case["query"], debug=True), tenant_id="acme")

    retrieved = {c.document_id for c in (resp.debug or [])}
    cited = {c.document_id for c in resp.citations}
    must = set(case["must_contain_sources"])
    must_not = set(case["must_not_contain_sources"])

    row = {
        "id": case["eval_id"], "category": case["category"], "status": resp.status.value,
        "reason": resp.refusal_reason, "latency_ms": resp.latency_ms,
        "context_recall": None, "citation_recall": None, "fact_recall": None,
        "faithfulness": None, "refusal_correct": None,
        "source_exclusion": not (must_not & (retrieved | cited)),
    }
    checks = {
        "excluded sources absent": row["source_exclusion"],
        "no forbidden text": all(f not in resp.answer.lower() for f in exp.get("forbidden", [])),
    }

    if exp["refuse"]:
        row["refusal_correct"] = resp.status in ("refused", "blocked") and not resp.citations
        checks["refused or blocked"] = row["refusal_correct"]
    else:
        facts = exp["facts"]
        row["context_recall"] = len(must & retrieved) / len(must) if must else 1.0
        row["citation_recall"] = len(must & cited) / len(must) if must else 1.0
        row["fact_recall"] = sum(_norm(f) in _norm(resp.answer) for f in facts) / len(facts)
        checks["answered"] = resp.status == "answered"
        checks["context recall = 1"] = row["context_recall"] == 1.0
        checks["citation recall = 1"] = row["citation_recall"] == 1.0
        checks["fact recall = 1"] = row["fact_recall"] == 1.0
        if resp.status == "answered":
            _, region_map = enrich_query(case["query"])
            row["faithfulness"], row["unsupported_claims"] = judge.score(
                resp.answer, [c.snippet for c in resp.citations], region_map
            )
            checks["faithfulness >= 0.9"] = row["faithfulness"] >= 0.9

    row["failed_checks"] = [name for name, ok in checks.items() if not ok]
    row["passed"] = not row["failed_checks"]
    report.append(row)  # record before asserting, so failures appear in the report too

    assert row["passed"], (
        f"{case['eval_id']} failed: {row['failed_checks']} | reason: {resp.refusal_reason} "
        f"| answer: {resp.answer[:200]!r}"
    )