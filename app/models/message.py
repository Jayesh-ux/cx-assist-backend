"""Message: a single turn in a conversation (customer or agent). Also the audit of the
AI generation lifecycle for that turn (draft, retrieved context, confidence, review action)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, String, Text

from app.db.base_class import Base


def gen_id() -> str:
    return str(uuid.uuid4())


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=gen_id)
    conversation_id = Column(String(36), ForeignKey("conversations.id"), nullable=False, index=True)
    brand_id = Column(String(36), ForeignKey("brands.id"), nullable=False, index=True)
    role = Column(String(16), nullable=False)          # customer | agent | ai_draft
    content = Column(Text, default="")
    # AI lifecycle fields (set once a generation happens):
    draft_text = Column(Text, default="")
    final_text = Column(Text, default="")
    status = Column(String(32), default="pending_review")  # pending_review|approved|edited|regenerated|manual|sent
    confidence = Column(Float, default=0.0)
    validation_code = Column(String(48), default="")
    context_sources = Column(Text, default="[]")   # JSON list of {source_url, policy_type, score}
    citation = Column(Text, default="")            # policy citation string
    human_note = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "id": self.id, "conversation_id": self.conversation_id, "brand_id": self.brand_id,
            "role": self.role, "content": self.content or "", "draft_text": self.draft_text or "",
            "final_text": self.final_text or "", "status": self.status, "confidence": self.confidence,
            "validation_code": self.validation_code or "", "context_sources": self.context_sources or "[]",
            "citation": self.citation or "", "human_note": self.human_note or "",
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }