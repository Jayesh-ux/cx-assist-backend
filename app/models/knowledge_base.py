"""Knowledge base: the indexed source-truth for a brand, with policy-type + source metadata."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.db.base_class import Base


def gen_id() -> str:
    return str(uuid.uuid4())


class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"

    id = Column(String(36), primary_key=True, default=gen_id)
    brand_id = Column(String(36), ForeignKey("brands.id"), nullable=False, index=True)
    source_id = Column(String(36), ForeignKey("brand_sources.id"), nullable=True, index=True)
    policy_type = Column(String(64), nullable=False, default="faq")
    title = Column(String(255), default="")
    source_url = Column(String(700), default="")
    content = Column(Text, default="")
    chunk = Column(Text, default="")          # the searchable unit
    chunk_index = Column(Integer, default=0)
    embedding_id = Column(String(64), default="")   # id in ChromaDB
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "id": self.id, "brand_id": self.brand_id, "source_id": self.source_id,
            "policy_type": self.policy_type, "title": self.title or "", "source_url": self.source_url or "",
            "content": self.content or "", "chunk": self.chunk or "", "chunk_index": self.chunk_index,
            "embedding_id": self.embedding_id or "", "created_at": self.created_at.isoformat() if self.created_at else None,
        }