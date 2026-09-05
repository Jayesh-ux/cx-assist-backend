"""Customer: an end consumer (optional lookup for order context in chat flow)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String

from app.db.base_class import Base


def gen_id() -> str:
    return str(uuid.uuid4())


class Customer(Base):
    __tablename__ = "customers"

    id = Column(String(36), primary_key=True, default=gen_id)
    brand_id = Column(String(36), ForeignKey("brands.id"), nullable=False, index=True)
    email = Column(String(255), default="", index=True)
    name = Column(String(120), default="")
    external_ref = Column(String(120), default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "id": self.id, "brand_id": self.brand_id, "email": self.email or "",
            "name": self.name or "", "external_ref": self.external_ref or "",
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }