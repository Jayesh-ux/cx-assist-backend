"""Website fetcher -> HTML cleaner -> policy extractor -> (external) chunk + index.

This is the OPTIONAL crawler. It uses httpx + a lightweight HTML cleaner
(regex-based stripping + basic readability extraction). For production, swap in
Trafilatura/BeautifulSoup readability. Errors are logged and do not crash the app.
"""
from __future__ import annotations

import re

import httpx

from app.core.logging import logger
from app.services.chunker import chunk_text
from app.services import vector_store

_HTML_TAGS = re.compile(r"<[^>]+>")
_SCRIPTS = re.compile(r"<(script|style|noscript|svg|head|header|footer|nav)[^>]*>.*?</\1>", re.S | re.I)
_MULTI_WS = re.compile(r"\s+")


def fetch_html(url: str) -> str:
    resp = httpx.get(url, timeout=30.0, follow_redirects=True,
                     headers={"User-Agent": "CXAssistBot/1.0 (policy crawler)"})
    resp.raise_for_status()
    return resp.text


def clean_html(html: str) -> str:
    html = _SCRIPTS.sub(" ", html)
    text = _HTML_TAGS.sub(" ", html)
    text = text.replace("&amp;", "&").replace("&nbsp;", " ").replace("&lt;", "<").replace("&gt;", ">")
    return _MULTI_WS.sub(" ", text).strip()


def extract_policy(text: str, max_len: int = 200000) -> str:
    """Heuristic 'policy extractor': pull paragraphs that look like policy/
    terms/faq/reply content. Keeps it simple + deterministic."""
    blocks = [b.strip() for b in re.split(r"\n{2,}", text) if len(b.strip()) > 20]
    keep = [b for b in blocks if re.search(r"\b(policy|terms|faq|return|refund|shipping|warranty|support|how do i|can i|help)\b", b, re.I)]
    return "\n\n".join(keep[:40])[:max_len]


def crawl_and_index(brand: str, url: str, source_id: str | None = None) -> int:
    """End-to-end optional crawl: fetch -> clean -> extract -> chunk -> index."""
    try:
        html = fetch_html(url)
        cleaned = clean_html(html)
        body = extract_policy(cleaned)
        chunks = chunk_text(body)
        count = vector_store.upsert_chunks(brand=brand, chunks=chunks, source=url)
        logger.info("crawl complete brand=%s url=%s chunks=%d", brand, url, count)
        return count
    except Exception as exc:  # noqa: BLE001
        logger.error("crawl failed brand=%s url=%s error=%s", brand, url, exc)
        return 0