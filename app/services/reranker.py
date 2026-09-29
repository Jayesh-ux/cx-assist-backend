"""Re-ranking: refine the coarse Top-K vector hits using a lightweight lexical +
positional scorer (BM25-style overlap + question-match). Simulates the second-stage
cross-encoder used in production RAG without a heavy model dependency."""
from __future__ import annotations

from app.core.config import settings
from app.services.vector_store import _lexical_score


def rerank(query: str, chunks: list[dict], top_n: int | None = None) -> list[dict]:
    """Return chunks re-sorted by a combined recency(query-overlap) + vector-score rank."""
    top_n = top_n or settings.top_k
    for c in chunks:
        # Deterministic stopword-aware token-overlap (reuses the vector-store scorer)
        lexical = _lexical_score(query, c.get("text", ""))
        c["rerank_score"] = round(0.4 * float(c.get("score", 0)) + 0.6 * lexical, 4)
    chunks.sort(key=lambda c: c.get("rerank_score", 0), reverse=True)
    return chunks[:top_n]