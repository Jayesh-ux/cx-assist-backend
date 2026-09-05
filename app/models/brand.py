"""Brand entity — the top-level tenancy/owner of all context and conversations."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, String, Text

from app.db.base_class import Base


def gen_id() -> str:
    return str(uuid.uuid4())


class Brand(Base):
    __tablename__ = "brands"

    id = Column(String(36), primary_key=True, default=gen_id)
    name = Column(String(120), unique=True, nullable=False, index=True)
    description = Column(Text, default="")
    website_url = Column(String(500), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description or "",
            "website_url": self.website_url or "",
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }