import json
import math
import time

from fastembed.rerank.cross_encoder import TextCrossEncoder

from app.config import settings
from app.retrieval.embeddings import Embedder
from app.retrieval.vector_store import VectorStore

MODELS = [
    "Xenova/ms-marco-MiniLM-L-6-v2",       # current: tiny and fast
    "jinaai/jina-reranker-v1-turbo-en",    # small, more semantic
    "BAAI/bge-reranker-base",              # larger, strongest, slowest
]

bench = json.load(open("data/benchmark_eval.json", encoding="utf-8"))
queries = [(c["eval_id"], c["query"]) for c in bench] + [
    ("EXTRA-A1", "Can engineers work from home every day?"),
    ("EXTRA-A2", "What is the monitor budget in Singapore?"),
    ("EXTRA-U1", "How many vacation days do I get?"),
    ("EXTRA-U2", "What is the dental insurance plan?"),
]

embedder = Embedder(settings.dense_model, settings.sparse_model)
store = VectorStore(settings.qdrant_url, settings.collection)
candidates = {
    qid: store.hybrid_search(*embedder.embed_query(q), "acme", False, settings.prefetch_k)
    for qid, q in queries
}

print("Supported re-rankers:", [m["model"] for m in TextCrossEncoder.list_supported_models()])

for name in MODELS:
    model = TextCrossEncoder(name)
    print(f"\n=== {name}")
    start = time.perf_counter()
    for qid, q in queries:
        points = candidates[qid]
        scores = list(model.rerank(q, [p.payload["text"] for p in points]))
        best = max(range(len(points)), key=lambda i: scores[i])
        prob = 1 / (1 + math.exp(-scores[best]))
        p = points[best].payload
        print(f"  {qid:9} top={prob:.4f}  raw={scores[best]:7.2f}  {p['doc_id']:16} {p['section']}")
    print(f"  time for all queries: {time.perf_counter() - start:.2f}s")