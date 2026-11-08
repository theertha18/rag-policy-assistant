from qdrant_client import QdrantClient, models


class VectorStore:
    """All communication with Qdrant lives here."""

    def __init__(self, url: str, collection: str, dim: int = 384):
        self.client = QdrantClient(url=url)
        self.collection = collection
        self.dim = dim

    def ensure_collection(self) -> None:
        """Create the collection once, with both vector types and filter indexes."""
        if self.client.collection_exists(self.collection):
            return
        self.client.create_collection(
            self.collection,
            vectors_config={"dense": models.VectorParams(size=self.dim, distance=models.Distance.COSINE)},
            sparse_vectors_config={"bm25": models.SparseVectorParams(modifier=models.Modifier.IDF)},
        )
        self.client.create_payload_index(self.collection, "tenant_id", models.PayloadSchemaType.KEYWORD)
        self.client.create_payload_index(self.collection, "doc_id", models.PayloadSchemaType.KEYWORD)
        self.client.create_payload_index(self.collection, "is_current", models.PayloadSchemaType.BOOL)

    def count(self) -> int:
        return self.client.count(self.collection).count

    def upsert(self, chunks, dense, sparse) -> None:
        """Insert chunks, or overwrite them if the same chunk_id already exists."""
        points = [
            models.PointStruct(
                id=c.chunk_id,
                vector={
                    "dense": d.tolist(),
                    "bm25": models.SparseVector(indices=s.indices.tolist(), values=s.values.tolist()),
                },
                payload={**c.metadata, "text": c.text},
            )
            for c, d, s in zip(chunks, dense, sparse)
        ]
        self.client.upsert(self.collection, points=points, wait=True)

    def hybrid_search(self, dense_q, sparse_q, tenant_id: str, include_superseded: bool, limit: int):
        """Search by meaning AND by exact words, then merge the two result lists."""
        must = [models.FieldCondition(key="tenant_id", match=models.MatchValue(value=tenant_id))]
        if not include_superseded:
            must.append(models.FieldCondition(key="is_current", match=models.MatchValue(value=True)))
        flt = models.Filter(must=must)

        sparse_vec = models.SparseVector(indices=sparse_q.indices.tolist(), values=sparse_q.values.tolist())
        result = self.client.query_points(
            self.collection,
            prefetch=[
                models.Prefetch(query=dense_q.tolist(), using="dense", filter=flt, limit=limit),
                models.Prefetch(query=sparse_vec, using="bm25", filter=flt, limit=limit),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            query_filter=flt,
            limit=limit,
            with_payload=True,
        )
        return result.points