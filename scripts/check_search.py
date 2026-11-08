from app.config import settings
from app.ingestion.pipeline import ingest_directory
from app.retrieval.embeddings import Embedder
from app.retrieval.vector_store import VectorStore

embedder = Embedder(settings.dense_model, settings.sparse_model)
store = VectorStore(settings.qdrant_url, settings.collection)
store.ensure_collection()

n = ingest_directory(settings.data_dir, settings.default_tenant, embedder, store)
print(f"Ingested {n} chunks | points in Qdrant: {store.count()}")


def show(question: str, tenant: str = "acme", include_superseded: bool = False):
    dense_q, sparse_q = embedder.embed_query(question)
    points = store.hybrid_search(dense_q, sparse_q, tenant, include_superseded, limit=5)
    print(f"\nQ: {question}  [tenant={tenant}, include_superseded={include_superseded}]")
    if not points:
        print("  (no results)")
    for p in points:
        print(f"  {p.score:.3f}  {p.payload['doc_id']:16} {p.payload['section']}")


show("What is the home office allowance?")
show("What is the home office allowance?", include_superseded=True)
show("What is the laptop allowance in EMEA?")
show("What is the home office allowance?", tenant="other-company")