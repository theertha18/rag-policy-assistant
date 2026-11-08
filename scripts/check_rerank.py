from app.config import settings
from app.retrieval.embeddings import Embedder
from app.retrieval.reranker import Reranker
from app.retrieval.vector_store import VectorStore

embedder = Embedder(settings.dense_model, settings.sparse_model)
store = VectorStore(settings.qdrant_url, settings.collection)
reranker = Reranker(settings.rerank_model)

questions = [
    "Can engineers work from home every day?",
    "What is the laptop allowance in EMEA?",
    "What is the company policy regarding paid parental leave duration and maternity benefits?",
]

for q in questions:
    dense_q, sparse_q = embedder.embed_query(q)
    points = store.hybrid_search(dense_q, sparse_q, "acme", False, settings.prefetch_k)
    ranked = reranker.rerank(q, points, top_k=3)
    print(f"\nQ: {q}")
    for point, score, raw in ranked:
        print(f"  {score:.4f}  raw={raw:7.2f}  {point.payload['doc_id']:16} {point.payload['section']}")