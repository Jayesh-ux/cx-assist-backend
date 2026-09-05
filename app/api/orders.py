"""Orders: create + look up orders (used to give the AI order-specific context)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.brand import Brand
from app.models.order import Order
from app.schemas.schemas import OrderLookup

router = APIRouter()


def _brand_or_404(db: Session, brand_id: str) -> Brand:
    b = db.get(Brand, brand_id)
    if not b:
        raise HTTPException(404, "Brand not found")
    return b


@router.post("/lookup")
def lookup(payload: OrderLookup, db: Session = Depends(get_db)):
    _brand_or_404(db, payload.brand_id)
    order = (db.query(Order).filter(Order.brand_id == payload.brand_id,
                                    Order.order_number == payload.order_number).first())
    if not order:
        return {"found": False, "order": None}
    return {"found": True, "order": order.to_dict()}