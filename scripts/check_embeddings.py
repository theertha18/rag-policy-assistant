import numpy as np

from app.config import settings
from app.retrieval.embeddings import Embedder

embedder = Embedder(settings.dense_model, settings.sparse_model)

texts = [
    "Tier 1 Roles (Engineering, Product, Architecture): Fully remote allowed without special manager sign-off.",
    "Region: EMEA; Laptop Allowance (Max): €1,800 EUR; Monthly Mobile Stipend: €60 EUR",
    "The home office stipend has been increased to $750 USD per calendar year.",
]
dense, sparse = embedder.embed_documents(texts)
print("Dense vector length:", len(dense[0]))
print("Sparse vector: non-zero entries:", len(sparse[0].indices))
print()

question = "Can engineers work from home every day?"
q_dense, _ = embedder.embed_query(question)
print("Question:", question)
for text, vec in zip(texts, dense):
    similarity = float(np.dot(q_dense, vec) / (np.linalg.norm(q_dense) * np.linalg.norm(vec)))
    print(f"  {similarity:.3f}  {text[:70]}")