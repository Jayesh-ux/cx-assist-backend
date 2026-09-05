"""ChromaDB-backed vector store with BRAND-ISOLATED retrieval.

Each document stores its `brand` in metadata. Retrieval ALWAYS filters by the
requested brand in the `where` clause — making cross-brand leakage impossible at
the storage layer, on top of the guardrail checks.

If ChromaDB is not installed (or its wheels can't build on this Python
version), the store transparently falls back to an in-memory fake that keeps
the same API surface — used for dev, smoke tests, and Render's free tier.
"""
from __future__ import annotations

import hashlib

from app.core.config import settings
from app.core.logging import logger
from app.services.embeddings import embed_text, embed_texts

_client = None
_use_real = False


class _MemoryStore:
    """In-memory fallback implementing the same collection API surface."""

    def __init__(self):
        self.docs = {}

    def upsert(self, ids=None, embeddings=None, documents=None, metadatas=None):
        for i, doc in enumerate(documents or []):
            self.docs[ids[i]] = {"text": doc, "meta": metadatas[i] if metadatas else {}}

    def get(self, where=None):
        brand = (where or {}).get("brand")
        src = None
        if where and "$and" in where:
            brand = where["$and"][0].get("brand")
            src = where["$and"][1].get("source")
        out = {
            "ids": [],
            "documents": [],
            "metadatas": [],
        }
        for cid, val in self.docs.items():
            m = val["meta"]
            if brand and m.get("brand") != brand:
                continue
            if src and m.get("source") != src:
                continue
            out["ids"].append(cid)
            out["documents"].append(val["text"])
            out["metadatas"].append(m)
        return out

    def delete(self, ids=None):
        for cid in ids or []:
            self.docs.pop(cid, None)

    def query(self, query_embeddings=None, n_results=None, where=None):
        brand = (where or {}).get("brand")
        vals = [v for v in self.docs.values()
                if v["meta"].get("brand") == brand] if brand else list(self.docs.values())
        vals = vals[: n_results or settings.top_k]
        return {
            "documents": [[v["text"] for v in vals]],
            "metadatas": [[v["meta"] for v in vals]],
            "distances": [[0.05] * len(vals)],
        }


class _MemoryClient:
    _singleton = None

    def __new__(cls):
        if cls._singleton is None:
            cls._singleton = super().__new__(cls)
            cls._singleton.cols = {}
        return cls._singleton

    def get_or_create_collection(self, name, **kw):
        self.cols.setdefault(name, _MemoryStore())
        return self.cols[name]

    def get_collection(self, name):
        if name not in self.cols:
            self.cols[name] = _MemoryStore()
        return self.cols[name]


def _get_client():
    global _client, _use_real
    if _client is not None:
        return _client
    try:
        import chromadb  # noqa: PLC0415

        _client = chromadb.HttpClient(host=settings.chroma_host, port=int(settings.chroma_port))
        _use_real = True
        logger.info("vector store: real ChromaDB at %s:%s", settings.chroma_host, settings.chroma_port)
    except Exception as exc:  # pragma: no cover - fallback path
        logger.warning("chromadb unavailable (%s); using in-memory fallback", exc)
        _client = _MemoryClient()
        _use_real = False
    return _client


def ensure_collection():
    try:
        col = _get_client().get_or_create_collection(
            settings.chroma_collection, metadata={"hnsw:space": "cosine"}
        )
        logger.info("vector store ready: %s", settings.chroma_collection)
        return col
    except Exception as exc:  # pragma: no cover
        logger.warning("chroma unavailable at startup: %s", exc)
        return None


def _collection():
    return _get_client().get_collection(settings.chroma_collection)


def upsert_chunks(brand: str, chunks: list[str], source: str) -> int:
    if not chunks:
        return 0
    col = _collection()
    ids = [_doc_id(brand, source, i) for i in range(len(chunks))]
    metas = [{"brand": brand, "source": source, "idx": i} for i in range(len(chunks))]
    emb = embed_texts(chunks)
    col.upsert(ids=ids, embeddings=emb, documents=chunks, metadatas=metas)
    logger.info("indexed %d chunks for brand=%s source=%s", len(chunks), brand, source)
    return len(chunks)


def delete_documents_by_source(brand: str, source: str) -> None:
    col = _collection()
    res = col.get(where={"$and": [{"brand": brand}, {"source": source}]})
    ids = res.get("ids", [])
    if ids:
        col.delete(ids=ids)
        logger.info("deleted %d chunks for source=%s", len(ids), source)


def delete_all_for_brand(brand: str) -> None:
    col = _collection()
    res = col.get(where={"brand": brand})
    ids = res.get("ids", [])
    if ids:
        col.delete(ids=ids)
        logger.info("deleted %d chunks for brand=%s", len(ids), brand)


def query(brand: str, query_text: str, top_k: int | None = None, score_threshold: float | None = None) -> list[dict]:
    """Semantic search that is ALWAYS brand-scoped via the where clause."""
    k = top_k or settings.top_k
    thr = score_threshold if score_threshold is not None else settings.score_threshold
    col = _collection()
    q = embed_text(query_text)
    res = col.query(query_embeddings=[q], n_results=k, where={"brand": brand})
    out: list[dict] = []
    for i, doc in enumerate(res.get("documents", [[]])[0]):
        meta = res.get("metadatas", [[]])[0][i]
        dist = res.get("distances", [[]])[0][i]
        score = 1.0 - dist  # cosine distance -> similarity
        if score >= thr:
            out.append({"text": doc, "brand": meta.get("brand"), "source": meta.get("source"), "score": round(score, 4)})
    return out


def _doc_id(brand: str, source: str, idx: int) -> str:
    raw = f"{brand}::{source}::{idx}"
    return hashlib.md5(raw.encode()).hexdigest()