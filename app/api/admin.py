"""Admin: dashboard stats, audit trail, AI logs, and a webhook receiver (optional)."""
from __future__ import annotations

import json
import logging

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.ai_log import AILog
from app.models.audit_log import AuditLog
from app.models.brand import Brand
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.order import Order

logger = logging.getLogger("cxassist")
router = APIRouter()


def require_admin(x_admin_key: str = Header(default="", alias="X-Admin-Key")):
    if not settings.admin_api_key or x_admin_key != settings.admin_api_key:
        raise HTTPException(403, "Invalid admin key")
    return True


@router.get("/stats", dependencies=[Depends(require_admin)])
def stats(db: Session = Depends(get_db)):
    brands = db.query(Brand).count()
    conversations = db.query(Conversation).count()
    messages = db.query(Message).count()
    orders = db.query(Order).count()
    by_status = {row[0]: row[1] for row in db.query(Message.status, func.count(Message.id))
                 .group_by(Message.status).all()}
    by_provider = {row[0]: row[1] for row in db.query(AILog.provider, func.count(AILog.id))
                   .group_by(AILog.provider).all()}
    avg_conf = db.query(func.avg(AILog.confidence)).scalar() or 0.0
    return {
        "brands": brands,
        "conversations": conversations,
        "messages": messages,
        "orders": orders,
        "replies_by_status": by_status,
        "llm_by_provider": by_provider,
        "avg_confidence": round(float(avg_conf), 3),
    }


@router.get("/audit", dependencies=[Depends(require_admin)])
def audit(limit: int = 100, db: Session = Depends(get_db)):
    rows = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [r.to_dict() for r in rows]


@router.get("/logs", dependencies=[Depends(require_admin)])
def llm_logs(limit: int = 100, db: Session = Depends(get_db)):
    rows = db.query(AILog).order_by(AILog.created_at.desc()).limit(limit).all()
    return [r.to_dict() for r in rows]


@router.post("/webhook", status_code=202)
async def webhook(request: Request):
    """Receive an external event (e.g. new support ticket) and optionally forward
    to an LLM/automation webhook. Demonstrates webhook support (fire-any-side)."""
    body = await request.body()
    logger.info("webhook received len=%s", len(body))
    if settings.webhook_url:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(settings.webhook_url, content=body)
        except Exception as exc:  # noqa: BLE001
            logger.warning("webhook forward failed: %s", exc)
            return {"status": "accepted", "forwarded": False}
    return {"status": "accepted", "forwarded": True}