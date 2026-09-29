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
import re
import uuid

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
            self.docs[ids[i]] = {
                "text": doc,
                "meta": metadatas[i] if metadatas else {},
            }

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
    ids = [f"{_doc_id(brand, source, i)}-{uuid.uuid4().hex[:12]}" for i in range(len(chunks))]
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
    """BRAND-scoped search. Uses ChromaDB semantic search when available, or a
    deterministic lexical (token-overlap) ranker in the in-memory fallback."""
    global _use_real
    k = top_k or settings.top_k
    thr = score_threshold if score_threshold is not None else settings.score_threshold
    col = _collection()

    if not _use_real:
        res = col.get(where={"brand": brand})
        docs = res.get("documents", [])
        metas = res.get("metadatas", [])
        ranked = sorted(zip(docs, metas), key=lambda t: _lexical_score(query_text, t[0]), reverse=True)
        out = []
        for doc, meta in ranked[:k]:
            score = _lexical_score(query_text, doc)
            if score >= thr:
                out.append({"text": doc, "brand": meta.get("brand"),
                            "source": meta.get("source"), "score": round(score, 4)})
        return out

    q = embed_text(query_text)
    res = col.query(query_embeddings=[q], n_results=k, where={"brand": brand})
    out: list[dict] = []
    for i, doc in enumerate(res.get("documents", [[]])[0]):
        meta = res.get("metadatas", [[]])[0][i]
        dist = res.get("distances", [[]])[0][i]
        cosine = 1.0 - dist  # cosine distance -> similarity
        lexical = _lexical_score(query_text, doc)
        score = max(cosine, lexical)  # blend deterministic token-overlap when it is stronger
        if score >= thr:
            out.append({"text": doc, "brand": meta.get("brand"), "source": meta.get("source"), "score": round(score, 4)})
    return out


def _doc_id(brand: str, source: str, idx: int) -> str:
    raw = f"{brand}::{source}::{idx}"
    return hashlib.md5(raw.encode()).hexdigest()


_STOPWORDS = frozenset(
    "a an the and or but if then else for of to in on with at by from up about into over after"
    " i you we they he she it this that these those my your his her its our their what which who"
    " is are was were be been being do does did done have has had can could will would shall should"
    " may might must not no yes so very just really please thanks thank want need get got going"
    .split()
)


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _stem(word: str) -> str:
    for suf in ("ing", "ies", "ed", "es", "er", "s"):
        if len(word) > 4 and word.endswith(suf):
            return word[: -len(suf)]
    return word


def _words(text: str) -> list[str]:
    out = []
    for t in _tokens(text):
        if t not in _STOPWORDS:
            out.append(_stem(t))
    return out


def _lexical_score(query_text: str, doc_text: str) -> float:
    """Deterministic token-overlap score used by the memory fallback store.

    The fallback keeps ChromaDB's API surface but ranks candidates by lexical
    overlap (BM25-style) because the local hash embedding is not a stable
    cosine metric; ChromaDB itself is used when available.

    Boosts exact/partial matches, rewards rare (non-stopword) query terms,
    and slightly better matches term distance for multi-word phrases."""
    q = _words(query_text)
    d = _words(doc_text)
    if not q:
        return 0.0
    dc = {}
    for t in d:
        dc[t] = dc.get(t, 0) + 1
    overlap = 0.0
    matched = set()
    for t in q:
        if t in dc and t not in matched:
            overlap += 1.0 + 0.25 * min(dc[t], 1)  # presence counts most
            matched.add(t)
    # Query-phrase (bigram) bonus: reward exact multi-word phrases shared with the doc.
    if len(q) > 1:
        qset = set(zip(q, q[1:]))
        dset = set(zip(d, d[1:]))
        overlap += 0.3 * len(qset & dset)
    precision = overlap / len(q)
    return round(min(1.0, precision), 4)