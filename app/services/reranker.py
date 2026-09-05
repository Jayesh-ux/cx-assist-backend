"""Re-ranking: refine the coarse Top-K vector hits using a lightweight lexical +
positional scorer (BM25-style overlap + question-match). Simulates the second-stage
cross-encoder used in production RAG without a heavy model dependency."""
from __future__ import annotations

import re
from collections import Counter

from app.core.config import settings


def _terms(text: str) -> Counter:
    return Counter(re.findall(r"[a-z0-9]+", text.lower()))


def rerank(query: str, chunks: list[dict], top_n: int | None = None) -> list[dict]:
    """Return chunks re-sorted by a combined recency(query-overlap) + vector-score rank."""
    top_n = top_n or settings.top_k
    q_terms = _terms(query)
    q_total = sum(q_terms.values()) or 1
    for c in chunks:
        c_terms = _terms(c.get("text", ""))
        overlap = sum(min(v, c_terms.get(t, 0)) for t, v in q_terms.items())
        # Jaccard-ish overlap ratio weighted with the original vector score
        lexical = overlap / q_total
        c["rerank_score"] = round(0.6 * float(c.get("score", 0)) + 0.4 * min(lexical, 1.0), 4)
    chunks.sort(key=lambda c: c.get("rerank_score", 0), reverse=True)
    return chunks[:top_n]