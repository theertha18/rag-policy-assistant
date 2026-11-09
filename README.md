# Policy RAG API

A containerized REST API that answers questions about company policy documents with **grounded answers, source citations, and deterministic refusal**. Built for the Atlantic Ventures AI Developer Challenge (Part B).

The core design principle: **the LLM only writes the sentence. Code decides what it sees and whether its answer is allowed out.** Every benchmark category is handled by a deterministic control, not by hoping the model behaves.

## Quickstart

Requirements: Docker Desktop and an LLM API key (any OpenAI-compatible endpoint; developed with Google Gemini).

```bash
cp .env.example .env          # then put your API key in .env
docker compose up --build -d  # first build takes a few minutes (models are baked into the image)
```

Open **http://localhost:8000/docs** for the interactive API, or:

```bash
curl -X POST http://localhost:8000/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the laptop allowance for an engineer based in Germany?", "debug": true}'
```

| Task | Make (Mac/Linux) | Plain command (any OS) |
|---|---|---|
| Start | `make up` | `docker compose up --build -d` |
| Unit tests (offline) | `make test` | `python -m pytest` |
| Benchmark evaluation | `make eval` | `python -m pytest tests/eval -m eval -v --tb=short` |
| Run the 5 benchmark questions | `make demo` | `python -m scripts.demo` |
| Stop | `make down` | `docker compose down` |

Local development: `python -m venv .venv`, activate it, `pip install -r requirements.txt -r requirements-dev.txt`.

## API

| Endpoint | Purpose |
|---|---|
| `POST /v1/query` | Ask a question. Body: `query` (1–2000 chars), optional `top_k`, `debug`, `include_superseded` |
| `GET /health` | Liveness: the process is running |
| `GET /ready` | Readiness: Qdrant reachable and documents indexed |

Every response has a `status` of **`answered`**, **`refused`** or **`blocked`**, so clients branch on a field, not on answer text. Refusals carry a named `refusal_reason` (`insufficient_context`, `not_in_context`, `output_validation_failed`, `prompt_injection_detected`). Citations include `document_id`, `section`, `relevance_score` (0–1) and the cited passage. Each response has a `trace_id` that also appears in the logs.

The tenant comes from the `X-Tenant-ID` header in this demo. **In production it would come from a verified JWT claim, never from client input.** If the LLM times out or is unavailable, the API returns a clean `503`.

## Architecture

```
question
  → input guard ............ injection patterns              → BLOCKED (no search, no LLM)
  → query enrichment ....... country → region (Germany → EMEA)
  → hybrid search .......... BM25 + dense, RRF fusion, pre-filtered by tenant and is_current
  → cross-encoder re-rank .. score each chunk against the question
  → gate 1 ................. best score below threshold       → REFUSED (no LLM call)
  → LLM .................... grounded answer as JSON, with source labels
  → gate 2 ................. LLM says "not answerable"        → REFUSED
  → output validator ....... citations exist, every number appears in cited text → else REFUSED
  → ANSWERED, with citations from the chunks actually used
```

**Ingestion** (automatic at startup if the store is empty): parse `KEY: value` headers into metadata, strip hidden HTML comments, resolve supersession from explicit `Supersedes <DOC-ID>` links, chunk prose by numbered section and tables by row (column names repeated in every row), embed with dense and sparse models, upsert with deterministic IDs (idempotent re-ingestion).

**Stack:** FastAPI + Pydantic v2 · Qdrant (hybrid dense + sparse search) · fastembed (local ONNX models: `BAAI/bge-small-en-v1.5`, `Qdrant/bm25`, `Xenova/ms-marco-MiniLM-L-6-v2`) · Gemini (`gemini-3.5-flash-lite`) via its OpenAI-compatible endpoint · pytest · Docker Compose.

## How each benchmark category is handled

| Category | Naive failure | Control in this system |
|---|---|---|
| Temporal conflict (TEST-01) | Both 2024 ($500, 2 days) and 2025 ($750, fully remote) retrieved | Superseded documents excluded **before scoring** (`is_current` pre-filter) |
| Tabular extraction (TEST-02) | Table split mid-row; US figures returned | One chunk per row with headers; explicit country → region map |
| Unanswerable (TEST-03) | Generic answer from model memory | Re-ranker threshold refuses **before any LLM call**; LLM answerability check as second gate |
| Multi-doc synthesis (TEST-04) | Only one document used | Hybrid search + re-ranking; prompt requires every part answered; numeric grounding per cited source |
| Prompt injection (TEST-05) | Prompt leaked or "APPROVED" returned | Input guard blocks; context delimited as data; LLM has no authority; output validator and leak marker |

## Evaluation

**Benchmark harness** (`tests/eval`): runs the real system on the 5 provided cases plus 5 extra cases (paraphrase, country → region table lookup, two more unanswerable questions, another injection). Per case it measures:

| Metric | Meaning |
|---|---|
| Context recall | Required documents found by retrieval |
| Citation recall | Required documents cited in the answer |
| Fact recall | Key facts present (e.g. €1,800, $750) |
| Faithfulness | LLM-as-judge: share of answer claims supported by the cited text |
| Source exclusion | Forbidden documents (the superseded 2024 policy) never retrieved or cited |
| Refusal correctness | Refused or blocked exactly when expected, with no citations |

### Results

**10/10 cases pass. Context recall, citation recall and fact recall are 1.00 on every answerable case; mean faithfulness is 1.00.** Model: `gemini-3.5-flash-lite`. Full table: [`reports/benchmark_report.md`](reports/benchmark_report.md).

| Outcome | Cases | Latency |
|---|---|---|
| Answered | TEST-01, 02, 04, EXTRA-A1, A2 | 0.9–2.1 s |
| Refused (gate 1, no LLM call) | TEST-03, EXTRA-U1, U2 | 0.17–0.29 s |
| Blocked (input guard) | TEST-05, EXTRA-I1 | 1 ms |

The latency gap is visible evidence that refusal and blocking are decided by code: those cases never reach the LLM. LLM outages (rate limits, timeouts) are recorded in the report as infrastructure errors, separately from wrong answers.

**Unit tests** (`tests/unit`, 56 tests, offline, no key): every component plus the service and API with fakes. Key proofs: a refused question **never calls the LLM** (`FakeLLM.calls == 0`); attacks never reach search; invented numbers are rejected; tenant and version filters always reach the store; LLM failure returns 503.

### Findings the evaluation surfaced, and the fixes

- **Re-ranker choice by data.** Compared three cross-encoders on the benchmark plus extra cases ([`reports/reranker_comparison.txt`](reports/reranker_comparison.txt)). Jina turbo could not separate answerable from unanswerable at all. BGE-base and MiniLM both could, with similar margins, but MiniLM was ~10× faster and ~12× smaller. Chosen: MiniLM, threshold at raw score −10.0 (lowest answerable −9.50, highest unanswerable −10.54).
- **Narrow margin → two gates.** Because the threshold margin is small and multi-part or paraphrased questions score lowest, gate 1 is set recall-first (only blocks clearly unrelated questions) and the LLM answerability check catches the rest.
- **Country mapping.** Adding the deterministic Germany → EMEA mapping raised the re-ranker score of the correct table row from 0.75 to 4.91.
- **Prompt fixes found by evaluation:** the model refused "Germany" because the region mapping wasn't inside `<sources>` (now declared as trusted configuration); refused "AI Software Engineer" until allowed to apply a rule to a case that clearly falls under it; and the smaller model omitted the $750 in the multi-document case until required to answer every part. All fixes are general rules, re-checked in both directions (parental leave is still refused), and TEST-04 was re-run three times to confirm stability.
- **Validator false positive.** The model wrote source labels like "(S1)" in the answer, and the numeric check flagged the digits. The system failed safe (refused), and now ignores labels and list numbering, with a unit test proving invented numbers are still caught.
- **Model latency and quotas.** One newer Gemini model took 88 s per request on the free tier; measured several and chose one answering in about 1–2 s ([`reports/llm_latency_check.txt`](reports/llm_latency_check.txt)). Free-tier daily quotas were hit during testing; the client retries rate limits with exponential backoff, and the provider is pure configuration.

## Design decisions and trade-offs

| Decision | Why | Alternative considered |
|---|---|---|
| Plain Python orchestration, no LangChain | Every step visible and unit-testable | Frameworks hide retrieval and prompt logic and add version churn |
| Qdrant | Native hybrid search, payload pre-filtering, sharding and quantization for scale | Chroma (weaker filtering), FAISS (no persistence or filters), pgvector (hybrid needs hand-built fusion) |
| Hybrid search **and** re-ranking | BM25 catches IDs and codes, dense catches paraphrase, re-ranker gives usable scores | Dense-only misses exact terms; re-ranking alone can only reorder what was found |
| Local ONNX models via fastembed | No second API key, deterministic, small image, offline after build | API embeddings cost per call; sentence-transformers pulls PyTorch (~2 GB) |
| Hard filter for superseded documents | Deterministic; old policy can never reach the model | Soft down-ranking can still leak; "prefer newer" prompting depends on the model |
| Refusal by code first | The brief requires deterministic refusal | LLM-only refusal is not deterministic |
| Custom pytest harness | No framework churn, runs in CI, every metric explainable | RAGAS / DeepEval: recognizable, but frequent API changes and opaque prompts |
| Provider behind an adapter | Switching providers or models is configuration (done during development) | Hard-coding one SDK into the service |
| Few retries in the API, more in evaluation | Users shouldn't wait a minute; a batch evaluation can | One retry policy for both |

## Security

- **Tenant isolation:** tenant and currency filters are applied **inside** both retrieval branches **and** on the fused result. Other tenants' and superseded chunks are never scored (pre-filtering, defense in depth).
- **Injection defense in layers:** input pattern guard (normalizes Unicode and zero-width characters; tested against false positives too), HTML comments stripped at ingestion, context delimited as data, the LLM has no tools or authority, output validation, and a random leak marker in the system prompt.
- **Container:** non-root user; no secrets in the image (`.env` excluded via `.dockerignore`, passed at runtime); Debian and Python packaging updates applied at build time. A Docker Scout scan of the base image showed 4 high findings; this image has 1, reported from pip's bundled SBOM (pip vendors `pkg_resources` from setuptools 70.3.0, CVE-2025-47273). The vulnerable module (`package_index`) isn't part of what pip vendors, and pip isn't used at runtime. In production: record a VEX "not affected" statement, remove pip from the runtime image, and scan every build in CI.

## Limitations

- **Small calibration set.** The refusal threshold was calibrated on ~10 queries; production needs a labelled set of hundreds and a precision/recall curve.
- **Faithfulness of 1.00 is on 5 answered cases** and judged by the same model family that generates answers, which may be lenient. A stronger, different judge and human-labelled checks are needed before trusting the number at scale.
- **Heuristic injection guard** will miss creative rephrasings; layered defenses limit the impact.
- **Manual country → region map**; in production this comes from HR configuration.
- **Whole-document supersession.** The 2024 policy's "Partial Invalidation" status hints at section-level overrides, which this version does not model.
- **Strict numeric grounding** refuses correct but *derived* numbers (e.g. a monthly figure computed from an annual one). Deliberately the safer error for policy answers.
- **Multi-part questions score low per chunk** (each chunk answers only half), which is why their relevance scores look low even when the answer is correct.
- **LLM output varies between runs** even at temperature 0; checks target facts and status, not wording.

## Scaling to 10M+ documents

1. **Size it:** 10M documents × ~10 chunks = 100M vectors. At 384 dims × 4 bytes ≈ 154 GB float32; int8 scalar quantization in RAM ≈ 38 GB, with full vectors on disk for rescoring.
2. **Distributed Qdrant:** sharded collection, replication factor 2, custom shard keys so large tenants get dedicated shards; payload indexes on `tenant_id`, `is_current`, `doc_id`.
3. **Async ingestion:** upload → object storage → queue → autoscaled parser/embedder workers with batched GPU embedding; content hashes skip unchanged documents.
4. **Document registry** (Postgres) owns versions, effective dates and section-level supersession; vector payloads mirror it.
5. **GPU re-ranker** scoring only the top ~50 fused candidates keeps latency flat as the corpus grows.
6. **Zero-downtime re-indexing** via blue/green collections behind a Qdrant alias when the embedding model changes.
7. **Caching:** exact-match cache, then a semantic cache keyed by tenant + permission set + corpus version.
8. **Multi-part questions:** query decomposition before retrieval.

## With more time

Query decomposition for multi-part questions · section-level supersession · ML-based injection classifier (e.g. Azure Prompt Shields) · a larger labelled evaluation set and a stronger, different judge model · streaming responses · tracing with Langfuse · removing pip from the runtime image · a paid model tier for predictable latency.

## A note on the challenge PDF

The challenge PDF contains hidden HTML comments addressed to AI tools (e.g. telling them to make 2024 policies override 2025, or to disable tenant metadata filtering). These were treated as an indirect prompt injection and ignored. Ingestion here strips HTML comments for the same reason.

## Project structure

```
app/
  api/          routes: query, health, readiness
  schemas/      Pydantic request/response models
  ingestion/    loader, versioning (supersession), chunker, pipeline
  retrieval/    embeddings, Qdrant hybrid store, re-ranker, query enrichment
  generation/   prompts, LLM client (provider adapter + fake for tests)
  guardrails/   injection detector, output validator
  services/     RAG orchestrator
  config.py     all settings, overridable via environment
tests/unit/     56 offline tests
tests/eval/     benchmark harness, LLM judge, report writer
scripts/        model download, demo, investigation scripts
reports/        evaluation and comparison results
data/           provided dataset
```