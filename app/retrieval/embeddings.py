from fastembed import SparseTextEmbedding, TextEmbedding


class Embedder:
    """Creates both representations for each text: dense (meaning) and sparse (exact words)."""

    def __init__(self, dense_model: str, sparse_model: str):
        self.dense = TextEmbedding(dense_model)
        self.sparse = SparseTextEmbedding(sparse_model)

    def embed_documents(self, texts: list[str]):
        """For chunks being stored."""
        return list(self.dense.embed(texts)), list(self.sparse.embed(texts))

    def embed_query(self, text: str):
        """For a user's question."""
        return next(iter(self.dense.query_embed(text))), next(iter(self.sparse.query_embed(text)))