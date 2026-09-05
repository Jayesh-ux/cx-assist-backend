"""ai_logs: per-generation telemetry (prompt, response, latency, model, tokens)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text

from app.db.base_class import Base


def gen_id() -> str:
    return str(uuid.uuid4())


class AILog(Base):
    __tablename__ = "ai_logs"

    id = Column(String(36), primary_key=True, default=gen_id)
    request_id = Column(String(64), nullable=False, index=True)
    brand_id = Column(String(36), ForeignKey("brands.id"), nullable=True, index=True)
    conversation_id = Column(String(36), ForeignKey("conversations.id"), nullable=True, index=True)
    model_used = Column(String(64), default="")
    provider = Column(String(32), default="")
    prompt_text = Column(Text, default="")
    customer_message = Column(Text, default="")
    retrieved_chunks = Column(Text, default="[]")
    llm_response = Column(Text, default="")
    edited_response = Column(Text, default="")
    final_response = Column(Text, default="")
    confidence = Column(Float, default=0.0)
    latency_ms = Column(Integer, default=0)
    token_usage = Column(Integer, default=0)
    status = Column(String(32), default="generated")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "id": self.id, "request_id": self.request_id, "brand_id": self.brand_id,
            "conversation_id": self.conversation_id, "model_used": self.model_used,
            "provider": self.provider, "customer_message": self.customer_message or "",
            "retrieved_chunks": self.retrieved_chunks or "[]", "llm_response": self.llm_response or "",
            "edited_response": self.edited_response or "", "final_response": self.final_response or "",
            "confidence": self.confidence, "latency_ms": self.latency_ms, "token_usage": self.token_usage,
            "status": self.status, "created_at": self.created_at.isoformat() if self.created_at else None,
        }