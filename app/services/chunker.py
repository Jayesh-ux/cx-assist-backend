"""Chunking engine: split long documents into overlapping, sentence-safe chunks
that also preserve the source policy boundaries for retrieval quality."""
from __future__ import annotations

import re

from app.core.config import settings


def chunk_documents(docs: list[str]) -> list[str]:
    out: list[str] = []
    for d in docs:
        out.extend(chunk_text(d))
    return out


def chunk_text(text: str, size: int | None = None, overlap: int | None = None) -> list[str]:
    size = size or settings.chunk_size
    overlap = overlap or settings.chunk_overlap
    sentences = _split_sentences(text)
    chunks: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for s in sentences:
        s_len = len(s)
        if cur_len + s_len > size and cur:
            chunks.append(" ".join(cur))
            # carry overlap from tail of previous chunk
            carry = _tail_chars(" ".join(cur), overlap)
            cur = carry.split(" ") if carry else []
            cur_len = len(" ".join(cur))
        cur.append(s)
        cur_len += s_len
    if cur:
        chunks.append(" ".join(cur))
    return [c.strip() for c in chunks if c.strip()]


def _split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text)
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _tail_chars(text: str, n: int) -> str:
    return text[-n:] if len(text) > n else text