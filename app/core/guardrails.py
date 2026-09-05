"""
Guardrails — the NON-NEGOTIABLE safety layer.

Enforces:
  1. No cross-brand leakage: a brand's context can never be retrieved/searched by another brand.
  2. No hallucination: the reply must only use retrieved context; if context is insufficient the
     assistant MUST say "I couldn't find enough info. Please review manually."
  3. Confidence gating: low-confidence replies are routed to human review instead of auto-send.

These checks run at EVERY stage: retrieval, prompt, generation, and post-validation.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ValidationCode(str, Enum):
    OK = "ok"
    NO_CONTEXT = "no_context"
    LOW_CONFIDENCE = "low_confidence"
    CROSS_BRAND = "cross_brand"
    UNGROUNDED = "ungrounded"


@dataclass
class ValidationResult:
    ok: bool
    code: ValidationCode
    confidence: float
    reason: str = ""


# Phrases that mark a "fallback" reply (guardrail trigger).
_FALLBACK_PHRASES = (
    "couldn't find enough info",
    "i couldn't find enough info",
    "please review manually",
    "not enough information",
    "i don't have the information",
    "review manually",
)


def is_fallback_reply(reply: str) -> bool:
    r = (reply or "").strip().lower()
    return any(p in r for p in _FALLBACK_PHRASES)


def validate_context_brand(context_brand: str | None, requested_brand: str | None) -> str | None:
    """Return an error string if the brand on context doesn't match the requested brand."""
    if not requested_brand:
        return "brand_detect_missing"
    if context_brand and context_brand != requested_brand:
        return "cross_brand_leak_detected"
    return None


def finalize_reply(reply: str | None, confidence: float, has_context: bool) -> ValidationResult:
    """Post-generation gating. Decides OK vs manual-review routing."""
    text = (reply or "").strip()

    if not text:
        return ValidationResult(False, ValidationCode.UNGROUNDED, confidence, "empty reply")

    # The assistant itself signalled it could not answer safely -> always manual.
    if is_fallback_reply(text):
        return ValidationResult(False, ValidationCode.NO_CONTEXT, confidence, "assistant flagged insufficient context")

    if not has_context:
        return ValidationResult(False, ValidationCode.NO_CONTEXT, confidence, "no retrieved context available")

    if confidence < 0.60:
        return ValidationResult(False, ValidationCode.LOW_CONFIDENCE, confidence, "confidence below threshold - route to human review")

    return ValidationResult(True, ValidationCode.OK, confidence, "grounded in retrieved context")