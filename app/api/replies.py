"""Reply log / history for a brand (agent messages), exercised by admin + audit view.
Each entry is decorated with the originating customer message for a complete audit trail."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.brand import Brand
from app.models.message import Message

router = APIRouter()


@router.get("")
def list_replies(brand_id: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Message).filter(Message.role == "agent")
    if brand_id:
        q = q.filter(Message.brand_id == brand_id)
    rows = q.order_by(Message.created_at.desc()).limit(200).all()
    out = []
    for m in rows:
        brand = db.get(Brand, m.brand_id)
        d = m.to_dict()
        d["brand_name"] = brand.name if brand else ""
        # decorate with the first customer message in the same conversation
        cust = (db.query(Message).filter(Message.conversation_id == m.conversation_id,
                                         Message.role == "customer")
                .order_by(Message.created_at).first())
        d["customer_message"] = cust.content if cust else ""
        out.append(d)
    return out


@router.get("/{message_id}")
def get_reply(message_id: str, db: Session = Depends(get_db)):
    m = db.get(Message, message_id)
    if not m:
        raise HTTPException(404, "Message not found")
    brand = db.get(Brand, m.brand_id)
    d = m.to_dict()
    d["brand_name"] = brand.name if brand else ""
    return d