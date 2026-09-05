"""Embedding generation. Abstracted behind a single function so the model
provider (local, OpenAI, or OmniRoute) can be swapped without touching callers.

Uses local hashing-based deterministic dims as the zero-dependency default, and
(optionally) the configured OpenAI embedding endpoint when OMNIPATH is present.
"""
from __future__ import annotations

import hashlib

from app.core.config import settings


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Return dense vectors for each text.

    Default: a deterministic, dependency-free embedding (fast + offline).
    Swap for a real model (e.g. text-embedding-3-small) when OMNIPATH_API_KEY set.
    """
    if settings.omnipath_api_key:
        return _embed_openai(texts)
    return [_embed_local(t) for t in texts]


def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]


def _embed_local(text: str) -> list[float]:
    """Stable per-token n-gram hash embedding, normalised. Good enough for the
    semantic-similarity demonstration and totally offline-safe."""
    dim = settings.embedding_dim
    vec = [0.0] * dim
    tokens = text.lower().split()
    for tok in tokens:
        for n in (2, 3):
            if len(tok) >= n:
                for i in range(len(tok) - n + 1):
                    gram = tok[i:i + n]
                    h = int(hashlib.md5(gram.encode()).hexdigest()[:8], 16)
                    idx = h % dim
                    vec[idx] += 1.0 if (h >> 8) % 2 == 0 else -1.0
    _norm(vec)
    return vec


def _embed_openai(texts: list[str]) -> list[list[float]]:
    import httpx
    resp = httpx.post(
        "https://api.openai.com/v1/embeddings",
        headers={"Authorization": f"Bearer {settings.omnipath_api_key}"},
        json={"model": settings.embedding_model, "input": texts},
        timeout=60.0,
    )
    resp.raise_for_status()
    rows = sorted(resp.json()["data"], key=lambda d: d["index"])
    return [r["embedding"] for r in rows]


def _norm(v: list[float]) -> None:
    mag = sum(x * x for x in v) ** 0.5
    if mag:
        for i in range(len(v)):
            v[i] /= mag


def reindex_brand(brand_id: str | None) -> None:
    """Background job: re-index all knowledge documents of a brand (deletes the
    brand's vectors and re-upserts them). Best-effort; no-op if brand unknown."""
    if not brand_id:
        return
    from sqlalchemy.orm import Session
    from app.db.session import SessionLocal
    from app.models.brand import Brand
    from app.models.knowledge_base import KnowledgeBase
    from app.services import vector_store

    db: Session = SessionLocal()
    try:
        brand = db.get(Brand, brand_id)
        if not brand:
            return
        vector_store.delete_all_for_brand(brand.name)
        docs = db.query(KnowledgeBase).filter(KnowledgeBase.brand_id == brand_id).all()
        texts = [d.content or d.chunk or "" for d in docs if (d.content or d.chunk)]
        if texts:
            count = vector_store.upsert_chunks(brand=brand.name, chunks=texts, source="reindex")
            from app.core.logging import logger
            logger.info("reindexed brand=%s chunks=%d", brand.name, count)
    finally:
        db.close()