"""Order: an order/customer transaction. Provides retrievable context for order-specific queries."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, String

from app.db.base_class import Base


def gen_id() -> str:
    return str(uuid.uuid4())


class Order(Base):
    __tablename__ = "orders"

    id = Column(String(36), primary_key=True, default=gen_id)
    brand_id = Column(String(36), ForeignKey("brands.id"), nullable=False, index=True)
    customer_id = Column(String(36), ForeignKey("customers.id"), nullable=True, index=True)
    order_number = Column(String(64), default="", index=True)
    status = Column(String(32), default="placed")  # placed|shipped|delivered|returned|refunded|cancelled
    amount = Column(Float, default=0.0)
    ordered_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "id": self.id, "brand_id": self.brand_id, "customer_id": self.customer_id,
            "order_number": self.order_number or "", "status": self.status,
            "amount": self.amount,
            "ordered_at": self.ordered_at.isoformat() if self.ordered_at else None,
        }