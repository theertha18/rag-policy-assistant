import json
import logging

from app.config import settings
from app.generation.llm_client import OpenAICompatibleClient
from app.retrieval.embeddings import Embedder
from app.retrieval.reranker import Reranker
from app.retrieval.vector_store import VectorStore
from app.schemas.query import QueryRequest
from app.services.rag_service import RAGService

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

service = RAGService(
    embedder=Embedder(settings.dense_model, settings.sparse_model),
    store=VectorStore(settings.qdrant_url, settings.collection),
    reranker=Reranker(settings.rerank_model),
    llm=OpenAICompatibleClient(settings.llm_api_key, settings.llm_model, settings.llm_base_url),
    settings=settings,
)

for case in json.load(open("data/benchmark_eval.json", encoding="utf-8")):
    resp = service.answer(QueryRequest(query=case["query"], debug=True), tenant_id="acme")
    print(f"\n=== {case['eval_id']} | {resp.status.value} | reason={resp.refusal_reason} | {resp.latency_ms} ms")
    print("  answer:", resp.answer[:200].replace("\n", " "))
    for c in resp.citations:
        print(f"  cites: {c.document_id:16} {c.section:35} relevance={c.relevance_score}")
    print("  expected sources:", case["must_contain_sources"], "| must NOT:", case["must_not_contain_sources"])