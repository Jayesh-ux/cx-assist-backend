"""Detection of the brand mentioned in a customer message.

Heuristic, deterministic, and dependency-free: scores brand matches against the
message with word-overlap and domain recognition. A better (LLM-based) detector
can be dropped in behind this same interface.
"""
from __future__ import annotations

import re


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def detect_brand(brands: list[str], message: str) -> str | None:
    if not brands:
        return None
    msg = message.lower()
    best = None
    best_score = 0
    for b in brands:
        b_lower = b.lower()
        b_tokens = _tokens(b)
        # exact substring match of the full brand name or domain
        if b_lower and (b_lower in msg or b_lower.replace(" ", "") in msg.replace(" ", "")):
            return b
        # token-overlap scoring
        inter = len(b_tokens & _tokens(msg))
        if inter > best_score:
            best_score = inter
            best = b
    return best if best_score > 0 else None