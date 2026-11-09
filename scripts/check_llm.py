import secrets

from app.config import settings
from app.generation.llm_client import OpenAICompatibleClient
from app.generation.prompts import SYSTEM_PROMPT, build_user_prompt
from app.guardrails.output_validator import validate_output
from app.retrieval.embeddings import Embedder
from app.retrieval.query_enrichment import enrich_query
from app.retrieval.reranker import Reranker
from app.retrieval.vector_store import VectorStore

embedder = Embedder(settings.dense_model, settings.sparse_model)
store = VectorStore(settings.qdrant_url, settings.collection)
reranker = Reranker(settings.rerank_model)
llm = OpenAICompatibleClient(settings.llm_api_key, settings.llm_model, settings.llm_base_url)
marker = f"LM-{secrets.token_hex(8)}"


def ask(question: str):
    search_q, region_map = enrich_query(question)
    points = store.hybrid_search(*embedder.embed_query(search_q), "acme", False, settings.prefetch_k)
    ranked = reranker.rerank(search_q, points, top_k=settings.top_k)
    labelled = {f"S{i + 1}": point for i, (point, _, _) in enumerate(ranked)}

    out = llm.complete_json(SYSTEM_PROMPT.format(marker=marker), build_user_prompt(question, labelled, region_map))
    print(f"\nQ: {question}")
    print("  LLM JSON:", out)
    if out.get("answerable"):
        cited = [l for l in out.get("sources", []) if l in labelled]
        texts = {l: p.payload["text"] for l, p in labelled.items()}
        print("  validation:", validate_output(out.get("answer", ""), cited, texts, marker) or "PASS")
        print("  cited docs:", [labelled[l].payload["doc_id"] for l in cited])


ask("What is the laptop allowance and mobile stipend for an engineer based in Germany?")
ask("I am a new engineering hire in the US. How do I order my home office setup and what is my laptop budget?")
# Deliberately skipping gate 1 here, to test gate 2: the AI itself should refuse.
ask("What is the company policy regarding paid parental leave duration and maternity benefits?")