import logging
import secrets
import time
import uuid

from app.generation.prompts import SYSTEM_PROMPT, build_user_prompt
from app.guardrails.injection import detect_injection
from app.guardrails.output_validator import validate_output
from app.retrieval.query_enrichment import enrich_query
from app.schemas.query import AnswerStatus, Citation, QueryRequest, QueryResponse, RetrievedChunk

log = logging.getLogger("rag")

REFUSAL_TEXT = "I cannot answer this question based on the provided documents."
BLOCKED_TEXT = "This request cannot be processed. Instruction overrides are not permitted."


class LLMUnavailable(Exception):
    """The language model did not respond in time or returned an error."""


class RAGService:
    def __init__(self, embedder, store, reranker, llm, settings):
        self.embedder = embedder
        self.store = store
        self.reranker = reranker
        self.llm = llm
        self.s = settings
        self.leak_marker = f"LM-{secrets.token_hex(8)}"  # random secret, new on every start

    def answer(self, req: QueryRequest, tenant_id: str) -> QueryResponse:
        start = time.perf_counter()
        trace_id = uuid.uuid4().hex
        ranked: list[tuple] = []

        def respond(status: AnswerStatus, text: str, reason: str | None = None, citations=()):
            debug = None
            if req.debug:
                debug = [
                    RetrievedChunk(document_id=p.payload["doc_id"], section=p.payload["section"],
                                   relevance_score=round(score, 4))
                    for p, score, _ in ranked
                ]
            log.info("query_done trace_id=%s status=%s reason=%s", trace_id, status.value, reason)
            return QueryResponse(
                status=status, answer=text, citations=list(citations), refusal_reason=reason,
                trace_id=trace_id, latency_ms=int((time.perf_counter() - start) * 1000), debug=debug,
            )

        # 1. Door guard: attacks never reach search or the AI
        if hits := detect_injection(req.query):
            log.warning("injection_blocked trace_id=%s patterns=%s", trace_id, hits)
            return respond(AnswerStatus.BLOCKED, BLOCKED_TEXT, "prompt_injection_detected")

        # 2. Search: enrich, filtered hybrid search, re-rank
        search_q, region_map = enrich_query(req.query)
        dense_q, sparse_q = self.embedder.embed_query(search_q)
        points = self.store.hybrid_search(dense_q, sparse_q, tenant_id, req.include_superseded, self.s.prefetch_k)
        ranked = self.reranker.rerank(search_q, points, req.top_k)

        # 3. Gate 1: refuse clearly unrelated questions before any AI cost
        relevant = [(p, score) for p, score, raw in ranked if raw >= self.s.min_rerank_score]
        if not relevant:
            return respond(AnswerStatus.REFUSED, REFUSAL_TEXT, "insufficient_context")

        # 4. The AI writes the answer
        labelled = {f"S{i + 1}": (p, score) for i, (p, score) in enumerate(relevant)}
        try:
            out = self.llm.complete_json(
                SYSTEM_PROMPT.format(marker=self.leak_marker),
                build_user_prompt(req.query, {label: p for label, (p, _) in labelled.items()}, region_map),
            )
        except Exception as exc:
            log.exception("llm_failed trace_id=%s", trace_id)
            raise LLMUnavailable() from exc

        # 5. Gate 2: the AI itself says the sources don't answer it
        answer = str(out.get("answer", "")).strip()
        if not out.get("answerable") or not answer:
            return respond(AnswerStatus.REFUSED, REFUSAL_TEXT, "not_in_context")

        # 6. Inspector: citations and numbers must check out
        cited = [label for label in dict.fromkeys(out.get("sources", [])) if label in labelled]
        texts = {label: p.payload["text"] for label, (p, _) in labelled.items()}
        if errors := validate_output(answer, cited, texts, self.leak_marker):
            log.warning("output_rejected trace_id=%s errors=%s", trace_id, errors)
            return respond(AnswerStatus.REFUSED, REFUSAL_TEXT, "output_validation_failed")

        # 7. Success: build citations from the chunks the AI actually used
        citations = [
            Citation(
                document_id=labelled[label][0].payload["doc_id"],
                title=labelled[label][0].payload["title"],
                section=labelled[label][0].payload["section"],
                relevance_score=round(labelled[label][1], 4),
                snippet=labelled[label][0].payload["text"],
            )
            for label in cited
        ]
        return respond(AnswerStatus.ANSWERED, answer, citations=citations)
    