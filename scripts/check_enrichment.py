from app.config import settings
from app.retrieval.embeddings import Embedder
from app.retrieval.query_enrichment import enrich_query
from app.retrieval.reranker import Reranker
from app.retrieval.vector_store import VectorStore

# 1. The mapping itself
for q in ["Laptop budget in Germany?", "What is the US laptop cap?", "Can you tell us more?", "Parental leave?"]:
    print(f"{q!r:35} -> {enrich_query(q)}")

# 2. Effect on retrieval for the real TEST-02 question
embedder = Embedder(settings.dense_model, settings.sparse_model)
store = VectorStore(settings.qdrant_url, settings.collection)
reranker = Reranker(settings.rerank_model)

question = "What is the laptop allowance and mobile stipend for an engineer based in Germany?"
enriched, _ = enrich_query(question)
for label, q in [("original", question), ("enriched", enriched)]:
    points = store.hybrid_search(*embedder.embed_query(q), "acme", False, settings.prefetch_k)
    point, score, raw = reranker.rerank(q, points, top_k=1)[0]
    print(f"\n{label:9} raw={raw:6.2f}  top chunk: {point.payload['section']}")