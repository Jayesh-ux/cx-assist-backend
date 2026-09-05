"""Background job/retry worker. In production this runs as a separate process
consuming the Redis list; here it's a lightweight async loop started in lifespan.
In-memory fallback: jobs run inline at enqueue time."""
from __future__ import annotations

import asyncio
import json
import traceback

from app.core.config import settings
from app.core.logging import logger
from app.core.redis_client import _redis_available

QUEUE = "cx:jobs"
MAX_RETRIES = 3


async def _run_job(name: str, payload: dict) -> None:
    if name == "crawl_source":
        from app.services.crawler import crawl_and_index
        brand = payload.get("brand")
        url = payload.get("url")
        source_id = payload.get("source_id")
        if not brand or not url:
            return
        await asyncio.to_thread(crawl_and_index, brand=brand, url=url, source_id=source_id)
    elif name == "regenerate_embeddings":
        from app.services.embeddings import reindex_brand
        await asyncio.to_thread(reindex_brand, payload.get("brand_id"))
    else:
        logger.warning("unknown job %s", name)


async def worker_loop(stop_event) -> None:
    if not _redis_available:
        await stop_event.wait()
        return
    import redis as redis_lib

    r = redis_lib.Redis.from_url(settings.redis_url, decode_responses=True)
    while not stop_event.is_set():
        try:
            item = r.blpop("cx:jobs", timeout=1)
            if not item:
                continue
            job = json.loads(item[1])
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    await _run_job(job["name"], job["payload"])
                    break
                except Exception as exc:
                    logger.error("job %s attempt %d failed: %s", job["name"], attempt, exc)
                    if attempt == MAX_RETRIES:
                        traceback.print_exc()
        except Exception as exc:
            logger.error("worker error %s", exc)
            await asyncio.sleep(2)