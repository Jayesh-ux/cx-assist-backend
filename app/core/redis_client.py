"""Redis-backed utilities: cache, rate limiting (fixed window via INCR+EXPIRE),
and a lightweight retry/queue helper. Gracefully degrades to in-memory if Redis is
unavailable so the app still runs in low-resource/dev environments."""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from app.core.config import settings
from app.core.logging import logger

_redis = None

try:
    import redis as _redis_lib

    _redis = _redis_lib.Redis.from_url(settings.redis_url, decode_responses=True)
    _redis.ping()
    _redis_available = True
except Exception as exc:  # pragma: no cover
    _redis = None
    _redis_available = False
    logger.warning("Redis unavailable (%s); using in-memory fallback", exc)


class _MemoryStore:
    """Thread-safe-ish in-memory fallback (single-process dev)."""
    def __init__(self):
        self._d: dict[str, Any] = {}
        self._ttl: dict[str, float] = {}

    def get(self, key: str):
        if key in self._ttl and time.time() > self._ttl[key]:
            self._d.pop(key, None)
            self._ttl.pop(key, None)
        return self._d.get(key)

    def set(self, key: str, value: Any, ttl: int = 0):
        self._d[key] = value
        if ttl:
            self._ttl[key] = time.time() + ttl


_mem = _MemoryStore()


def cache_get(key: str) -> Any | None:
    if _redis_available:
        raw = _redis.get(key)
        return json.loads(raw) if raw else None
    return _mem.get(key)


def cache_set(key: str, value: Any, ttl: int = 300) -> None:
    # allow nested objects; callers pass JSON-serialisable values
    serialized = json.dumps(value, default=str)
    if _redis_available:
        _redis.set(key, serialized, ex=ttl)
    else:
        _mem.set(key, serialized, ttl)


def rate_limit_allowed(key: str, limit: int | None = None, window: int = 60) -> bool:
    limit = limit or settings.rate_limit_per_minute
    if _redis_available:
        current = _redis.incr(key)
        if current == 1:
            _redis.expire(key, window)
        return current <= limit
    count = _mem.get(key) or 0
    _mem.set(key, count + 1, window)
    return (count + 1) <= limit


async def enqueue_job(name: str, payload: dict) -> None:
    """Push a job to the retry/queue list. Without Redis, run it inline."""
    if _redis_available:
        _redis.rpush("cx:jobs", json.dumps({"name": name, "payload": payload, "ts": asyncio.get_event_loop().time()}))
    else:
        # in-memory: process inline (best-effort)
        from app.workers.jobs import dispatch
        dispatch(name, payload)


def get_retry_key(queue: str) -> list[dict]:
    if not _redis_available:
        return []
    items = _redis.lrange(queue, 0, -1)
    return [json.loads(i) for i in items]