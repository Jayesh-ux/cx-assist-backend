"""Conversation & reply-generation pipeline.

Core flow (all brand-isolated):
  customer message -> brand detect -> conversation created -> customer message stored
  -> order lookup (optional) -> semantic search -> context builder -> STRICT prompt
  -> LLM -> response validator -> confidence -> human review route -> AILog + audit.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.guardrails import finalize_reply
from app.core.logging import logger
from app.db.session import get_db
from app.models.ai_log import AILog
from app.models.brand import Brand
from app.models.conversation import Conversation
from app.models.customer import Customer
from app.models.message import Message
from app.models.order import Order
from app.schemas.schemas import ConversationCreateNew, GenerateReply
from app.services import vector_store
from app.services.brand_detect import detect_brand
from app.services.llm_service import complete
from app.services.prompt_builder import build_messages, FALLBACK_SENTENCE
from app.services.reranker import rerank

router = APIRouter()


def _brand_or_404(db: Session, brand_id: str) -> Brand:
    brand = db.get(Brand, brand_id)
    if not brand:
        raise HTTPException(404, "Brand not found")
    return brand


@router.post("", status_code=201)
def create_conversation(payload: ConversationCreateNew, db: Session = Depends(get_db)):
    brand = _brand_or_404(db, payload.brand_id)
    customer = None
    if payload.customer_email:
        customer = db.query(Customer).filter(
            Customer.brand_id == brand.id, Customer.email == payload.customer_email.lower()).first()
        if not customer:
            customer = Customer(brand_id=brand.id, email=payload.customer_email.lower())
            db.add(customer)
            db.flush()
    conv = Conversation(brand_id=brand.id, customer_id=customer.id if customer else None,
                        detected_brand_name=brand.name, status="open")
    db.add(conv)
    db.flush()
    db.add(Message(conversation_id=conv.id, brand_id=brand.id, role="customer", content=payload.customer_message))
    db.commit()
    return conv.to_dict()


@router.get("")
def list_conversations(db: Session = Depends(get_db)):
    convs = db.query(Conversation).order_by(Conversation.created_at.desc()).limit(100).all()
    return [c.to_dict() for c in convs]


@router.get("/{conv_id}")
def get_conversation(conv_id: str, db: Session = Depends(get_db)):
    conv = db.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    msgs = db.query(Message).filter(Message.conversation_id == conv_id).order_by(Message.created_at).all()
    return {"conversation": conv.to_dict(), "messages": [m.to_dict() for m in msgs]}


@router.get("/{conv_id}/history")
def conversation_history(conv_id: str, db: Session = Depends(get_db)):
    conv = db.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    msgs = db.query(Message).filter(Message.conversation_id == conv_id).order_by(Message.created_at).all()
    return [{"role": m.role, "content": m.content or m.final_text or m.draft_text or ""} for m in msgs]


@router.post("/generate")
async def generate_reply(payload: GenerateReply, request: Request, db: Session = Depends(get_db)):
    brand = _brand_or_404(db, payload.brand_id)
    request_id = getattr(request.state, "request_id", "unknown")

    # 1) brand detect + isolation (defensive)
    brands_all = [b.name for b in db.query(Brand).all()]
    detected = detect_brand(brands_all, payload.customer_message) or brand.name
    if settings.enforce_brand_isolation and detected != brand.name:
        logger.warning("cross-brand signal detected=%s isolated_to=%s", detected, brand.name)

    # 2) conversation + customer message
    conv = Conversation(brand_id=brand.id, detected_brand_name=detected, status="open")
    db.add(conv)
    db.flush()
    customer_msg = Message(conversation_id=conv.id, brand_id=brand.id, role="customer",
                           content=payload.customer_message, status="sent")
    db.add(customer_msg)
    db.flush()

    # 3) order lookup (optional) -> order-specific guardrail context
    order_ctx = _attempt_order_lookup(db, brand)

    # 4) semantic search (brand-isolated) + re-rank
    ctx = vector_store.query(brand=brand.name, query_text=payload.customer_message, top_k=settings.top_k)
    ctx = rerank(payload.customer_message, ctx, top_n=settings.top_k)
    sources = [{"source_url": c.get("source", ""), "policy_type": c.get("policy_type", ""),
                "score": round(float(c.get("rerank_score", c.get("score", 0))), 4)} for c in ctx]
    has_context = len(ctx) > 0
    # Policy citation: the highest-scoring source's title/url + policy type.
    citation = ""
    if has_context and ctx[0].get("source"):
        pt = ctx[0].get("policy_type", "") or "policy"
        citation = f"Source: {ctx[0].get('source')} ({pt})"

    # 5) strict prompt -> LLM (with order context merged)
    prompt = build_messages(brand.name, payload.customer_message, ctx)
    if order_ctx:
        prompt[-1]["content"] += f"\n\nOrder context:\n{order_ctx}"

    async def _telemetry(meta: dict):
        log = AILog(
            request_id=request_id, brand_id=brand.id, conversation_id=conv.id,
            provider=meta["provider"], model_used=meta["model"],
            customer_message=payload.customer_message,
            retrieved_chunks=json.dumps(sources or []),
            llm_response=meta.get("final", ""),
            latency_ms=meta.get("latency_ms", 0), token_usage=meta.get("token_usage", 0),
            status="generated",
        )
        db.add(log)
        db.commit()

    try:
        draft = await complete(prompt, on_complete=_telemetry)
    except RuntimeError as exc:
        draft = FALLBACK_SENTENCE
        logger.warning("llm not configured (%s); returning guardrail fallback", exc)

    # 6) response validator + confidence
    confidence = (ctx[0].get("rerank_score", ctx[0].get("score", 0)) if ctx else 0.0) * 0.9 + 0.1
    validation = finalize_reply(draft, min(confidence, 1.0), has_context)
    status = "approved" if validation.ok else "pending_review"

    ai_draft = Message(
        conversation_id=conv.id, brand_id=brand.id, role="agent",
        content="", draft_text=draft, final_text=draft if validation.ok else "",
        status=status, confidence=validation.confidence,
        validation_code=validation.code.value,
        context_sources=json.dumps(sources or []),
        citation=citation,
    )
    db.add(ai_draft)
    if validation.ok:
        conv.status = "pending_send"
    db.commit()

    return {
        "mode": "auto" if validation.ok else "human_review",
        "conversation": conv.to_dict(),
        "message": ai_draft.to_dict(),
        "validation": {"ok": validation.ok, "code": validation.code.value,
                       "confidence": validation.confidence, "reason": validation.reason},
    }


def _attempt_order_lookup(db: Session, brand: Brand) -> str | None:
    # Simple demo: return a recently placed order if one exists for the brand.
    order = db.query(Order).filter(Order.brand_id == brand.id).order_by(Order.ordered_at.desc()).first()
    if not order:
        return None
    return f"Recent order for customer: status={order.status}, amount={order.amount}, number={order.order_number}"