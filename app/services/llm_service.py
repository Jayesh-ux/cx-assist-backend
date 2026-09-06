"""LLM service with a provider abstraction: OmniRoute (primary) -> Gemini (fallback).

Configurable via env (LLM_PROVIDER). If the primary provider fails or is not
configured, we fall back to the next provider. Clean, dependency-injected,
and testable.
"""
from __future__ import annotations

import asyncio
import random
import time
from typing import Callable, Awaitable

import httpx

from app.core.config import settings
from app.core.logging import logger

OMNIPATH_URL = "https://omniroute.ai/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"


def _retryable(status: int) -> bool:
    return status in (408, 429) or status >= 500


async def _post_with_retry(client: httpx.AsyncClient, url: str, *, params=None, json=None, headers=None,
                           attempts: int = 4) -> httpx.Response:
    """POST with exponential backoff + jitter on transient (429/5xx) errors."""
    for i in range(attempts):
        try:
            resp = await client.post(url, params=params, json=json, headers=headers)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
            logger.warning("llm request failed (%s); retrying %d/%d", exc, i + 1, attempts)
            if i == attempts - 1:
                raise
            await asyncio.sleep(min(2 ** i, 8) + random.uniform(0, 0.5))
            continue
        if _retryable(resp.status_code) and i < attempts - 1:
            wait = float(resp.headers.get("Retry-After", 0) or 0)
            logger.warning("llm provider returned %s; backing off ~%.1fs before retry",
                           resp.status_code, wait or 2 ** i)
            await asyncio.sleep(wait or min(2 ** i, 8) + random.uniform(0, 0.5))
            continue
        return resp
    return resp  # pragma: no cover - unreachable via the loop above


async def _call_omniroute(messages: list[dict], temperature: float, max_tokens: int) -> dict:
    if not settings.omnipath_api_key:
        raise RuntimeError("OMNIPATH_API_KEY not configured")
    payload = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await _post_with_retry(client, OMNIPATH_URL, json=payload,
                                      headers={"Authorization": f"Bearer {settings.omnipath_api_key}"})
        resp.raise_for_status()
        data = resp.json()
    content = data["choices"][0]["message"]["content"].strip()
    tokens = int(data.get("usage", {}).get("total_tokens", 0))
    return {"text": content, "provider": "omniroute", "tokens": tokens}


async def _call_gemini(messages: list[dict], temperature: float, max_tokens: int) -> dict:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY not configured")
    # Use the configured model name in the URL
    model = settings.llm_model or "gemini-2.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    # Turn chat messages into a Gemini prompt
    prompt = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages)
    params = {"key": settings.gemini_api_key}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await _post_with_retry(client, url, params=params, json=payload)
        resp.raise_for_status()
        data = resp.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    tokens = len(prompt.split()) + len(text.split())
    return {"text": text, "provider": "gemini", "tokens": tokens}


async def complete(messages: list[dict], temperature: float | None = None,
                   max_tokens: int | None = None,
                   on_complete: Callable[[dict], Awaitable[None]] | None = None) -> str:
    """Generate a reply with automatic provider fallback. Returns final text and
    invokes on_complete(meta) for telemetry."""
    temperature = settings.temperature if temperature is None else temperature
    max_tokens = settings.max_tokens if max_tokens is None else max_tokens

    providers = []
    if settings.llm_provider in ("omniroute", "auto"):
        providers.append(_call_omniroute)
    if settings.llm_provider in ("gemini", "auto"):
        providers.append(_call_gemini)
    if not providers:
        providers = [_call_omniroute, _call_gemini]

    last_err = None
    start = time.perf_counter()
    for call in providers:
        try:
            result = await call(messages, temperature, max_tokens)
            meta = {
                "provider": result["provider"],
                "model": settings.llm_model,
                "latency_ms": int((time.perf_counter() - start) * 1000),
                "token_usage": result["tokens"],
            }
            if on_complete:
                await on_complete(meta)
            return result["text"]
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            logger.warning("provider %s failed: %s", getattr(call, "__name__", "?"), exc)
            continue
    raise RuntimeError(f"All LLM providers failed: {last_err}")