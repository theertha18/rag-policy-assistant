import logging, secrets, time, uuid
from app.schemas.query import QueryRequest, QueryResponse, AnswerStatus, Citation, RetrievedChunk
from app.guardrails.injection import detect_injection
from app.guardrails.output_validator import validate_output
from app.retrieval.query_enrichment import enrich_query
from app.generation.prompts import SYSTEM_PROMPT, build_user_prompt

log = logging.getLogger("rag")
REFUSAL_TEXT = "I cannot answer this question based on the provided documents."
BLOCKED_TEXT = "This request cannot be processed. Instruction overrides are not permitted."

class LLMUnavailable(Exception): ...

class RAGService:
    def __init__(self, embedder, store, reranker, llm, settings):
        self.embedder, self.store, self.reranker, self.llm, self.s = embedder, store, reranker, llm, settings
        self.leak_marker = f"LM-{secrets.token_hex(8)}"   # random per process

    def answer(self, req: QueryRequest, tenant_id: str) -> QueryResponse:
        t0, trace_id = time.perf_counter(), uuid.uuid4().hex

        def respond(status, text, reason=None, citations=(), ranked=()):
            debug = [RetrievedChunk(document_id=p.payload["doc_id"], section=p.payload["section"],
                                    relevance_score=round(s, 4)) for p, s in ranked] if req.debug else None
            log.info("query_done", extra={"trace_id": trace_id, "status": status, "reason": reason})
            return QueryResponse(status=status, answer=text, citations=list(citations), refusal_reason=reason,
                                 trace_id=trace_id, latency_ms=int((time.perf_counter() - t0) * 1000), debug=debug)

        # 1. Input guardrail: no retrieval, no LLM call for injection attempts
        if detect_injection(req.query):
            log.warning("injection_blocked", extra={"trace_id": trace_id})
            return respond(AnswerStatus.BLOCKED, BLOCKED_TEXT, "prompt_injection_detected")

        # 2. Retrieval: enrich, hybrid search with tenant + currency pre-filter, re-rank
        query, region_map = enrich_query(req.query)
        dense_q, sparse_q = self.embedder.embed_query(query)
        points = self.store.hybrid_search(dense_q, sparse_q, tenant_id, req.include_superseded, self.s.prefetch_k)
        ranked = self.reranker.rerank(query, points, req.top_k)

        # 3. Deterministic refusal gate, before any LLM cost
        relevant = [(p, s) for p, s in ranked if s >= self.s.min_relevance]
        if not relevant:
            return respond(AnswerStatus.REFUSED, REFUSAL_TEXT, "insufficient_context", ranked=ranked)

        # 4. Generation
        labelled = {f"S{i + 1}": ps for i, ps in enumerate(relevant)}
        try:
            out = self.llm.complete_json(SYSTEM_PROMPT.format(marker=self.leak_marker),
                                         build_user_prompt(req.query, labelled, region_map))
        except Exception as exc:
            log.exception("llm_failed", extra={"trace_id": trace_id})
            raise LLMUnavailable() from exc
        if not out.get("answerable"):
            return respond(AnswerStatus.REFUSED, REFUSAL_TEXT, "not_in_context", ranked=ranked)

        # 5. Output validation
        answer = str(out.get("answer", "")).strip()
        cited = [l for l in dict.fromkeys(out.get("sources", [])) if l in labelled]
        texts = {l: p.payload["text"] for l, (p, _) in labelled.items()}
        if errors := validate_output(answer, cited, texts, self.leak_marker):
            log.warning("output_rejected", extra={"trace_id": trace_id, "errors": errors})
            return respond(AnswerStatus.REFUSED, REFUSAL_TEXT, "output_validation_failed", ranked=ranked)

        citations = [Citation(document_id=labelled[l][0].payload["doc_id"], title=labelled[l][0].payload["title"],
                              section=labelled[l][0].payload["section"], relevance_score=round(labelled[l][1], 4),
                              snippet=labelled[l][0].payload["text"][:300]) for l in cited]
        return respond(AnswerStatus.ANSWERED, answer, citations=citations, ranked=ranked)