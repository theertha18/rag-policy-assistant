import math

from fastembed.rerank.cross_encoder import TextCrossEncoder


class Reranker:
    """Scores each (question, chunk) pair together, then keeps the best ones."""

    def __init__(self, model: str):
        self.model = TextCrossEncoder(model)

    def rerank(self, query: str, points: list, top_k: int) -> list[tuple]:
        """Returns (point, relevance_0_to_1, raw_score), best first."""
        if not points:
            return []
        raw_scores = [float(s) for s in self.model.rerank(query, [p.payload["text"] for p in points])]
        scored = [(p, 1 / (1 + math.exp(-s)), s) for p, s in zip(points, raw_scores)]
        return sorted(scored, key=lambda item: item[2], reverse=True)[:top_k]