"""Brand source: a website URL (or manual source) tracked for a brand + its per-source ingestion state."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from app.db.base_class import Base


def gen_id() -> str:
    return str(uuid.uuid4())


class BrandSource(Base):
    __tablename__ = "brand_sources"

    id = Column(String(36), primary_key=True, default=gen_id)
    brand_id = Column(String(36), ForeignKey("brands.id"), nullable=False, index=True)
    source_url = Column(String(700), nullable=False)
    policy_type = Column(String(64), nullable=False)  # return|refund|shipping|cancellation|warranty|exchange|faq
    title = Column(String(255), default="")
    status = Column(String(32), default="pending")  # pending|processing|indexed|failed
    chunk_count = Column(Integer, default=0)
    error = Column(String(500), default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "id": self.id, "brand_id": self.brand_id, "source_url": self.source_url,
            "policy_type": self.policy_type, "title": self.title or "", "status": self.status,
            "chunk_count": self.chunk_count, "error": self.error or "",
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class PolicyType:
    RETURN = "return"
    REFUND = "refund"
    SHIPPING = "shipping"
    CANCELLATION = "cancellation"
    WARRANTY = "warranty"
    EXCHANGE = "exchange"
    FAQ = "faq"

    ALL = [RETURN, REFUND, SHIPPING, CANCELLATION, WARRANTY, EXCHANGE, FAQ]