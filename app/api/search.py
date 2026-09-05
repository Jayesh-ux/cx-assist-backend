"""Semantic search against a brand's indexed context (exercised by the admin panel)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.brand import Brand
from app.schemas.schemas import SearchRequest
from app.services import vector_store

router = APIRouter()


@router.post("")
def search(payload: SearchRequest, db: Session = Depends(get_db)):
    brand = db.get(Brand, payload.brand_id)
    if not brand:
        raise HTTPException(404, "Brand not found")
    return {"brand": brand.name, "query": payload.query,
            "results": vector_store.query(brand.name, payload.query, top_k=payload.top_k)}