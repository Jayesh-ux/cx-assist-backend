"""Prompt construction. Builds the STRICT system+user prompt for the LLM.

Rules baked in:
  - Answer ONLY from the retrieved context. Never invent facts.
  - Never reference other brands' policies.
  - If context is missing/insufficient, reply verbatim with the fallback guardrail sentence.
"""
from __future__ import annotations

FALLBACK_SENTENCE = "I couldn't find enough info. Please review manually."


def build_messages(brand: str | None, customer_message: str, context: list[dict]) -> list[dict]:
    # Brand-isolated context block. If no brand known, still no cross-brand data is attached.
    ctx_text = "\n\n".join(
        f"[Doc {i + 1} | brand={c.get('brand') or 'unknown'}]\n{c.get('text', '')}"
        for i, c in enumerate(context)
    ) if context else "NO CONTEXT AVAILABLE."

    system = (
        "You are a customer-support reply assistant operating under strict guardrails.\n"
        "Rules (non-negotiable):\n"
        "1. Answer ONLY from the provided 'Retrieved Context'. Never invent, assume, or add facts.\n"
        "2. Never mention or reference material from any other brand.\n"
        "3. If the context does not contain the answer, reply verbatim with exactly:\n"
        f"   \"{FALLBACK_SENTENCE}\"\n"
        "4. Keep replies concise, friendly, and in the customer's tone.\n"
        f"Brand under discussion: {brand or 'unknown'}\n"
    )

    user = (
        f"Retrieved Context:\n{ctx_text}\n\n"
        f"Customer message:\n{customer_message}\n\n"
        "Write the reply."
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]