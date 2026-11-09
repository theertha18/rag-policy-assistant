"""Download all local models at image build time, so the container starts fast and offline."""
from fastembed import SparseTextEmbedding, TextEmbedding
from fastembed.rerank.cross_encoder import TextCrossEncoder

from app.config import settings

TextEmbedding(settings.dense_model)
SparseTextEmbedding(settings.sparse_model)
TextCrossEncoder(settings.rerank_model)
print("Models cached:", settings.dense_model, settings.sparse_model, settings.rerank_model)