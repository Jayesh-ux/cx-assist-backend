"""embeddings: registry mapping knowledge chunks to their vector-store ids + model used.
Vectors themselves live in ChromaDB; this table is the Postgres-side index/registry."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from app.db.base_class import Base


def gen_id() -> str:
    return str(uuid.uuid4())


class EmbeddingRecord(Base):
    __tablename__ = "embeddings"

    id = Column(String(36), primary_key=True, default=gen_id)
    brand_id = Column(String(36), ForeignKey("brands.id"), nullable=False, index=True)
    knowledge_id = Column(String(36), ForeignKey("knowledge_base.id"), nullable=True, index=True)
    vector_id = Column(String(64), default="", index=True)   # id in ChromaDB
    model = Column(String(64), default="")
    dimensions = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "id": self.id, "brand_id": self.brand_id, "knowledge_id": self.knowledge_id,
            "vector_id": self.vector_id or "", "model": self.model, "dimensions": self.dimensions,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }