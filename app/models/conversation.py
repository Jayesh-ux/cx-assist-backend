"""Conversation: the aggregate root tying a brand + customer + message thread + orders context.
Message turns live in the `messages` table. Conversation stores header/state metadata."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String

from app.db.base_class import Base


def gen_id() -> str:
    return str(uuid.uuid4())


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=gen_id)
    brand_id = Column(String(36), ForeignKey("brands.id"), nullable=False, index=True)
    customer_id = Column(String(36), ForeignKey("customers.id"), nullable=True, index=True)
    detected_brand_name = Column(String(120), default="")
    source_channel = Column(String(32), default="web")  # web|email|whatsapp|api
    status = Column(String(24), default="open")          # open|pending_review|resolved|closed
    external_ref = Column(String(120), default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "id": self.id, "brand_id": self.brand_id, "customer_id": self.customer_id,
            "detected_brand_name": self.detected_brand_name or "", "source_channel": self.source_channel,
            "status": self.status, "external_ref": self.external_ref or "",
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }