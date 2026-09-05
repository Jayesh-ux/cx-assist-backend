"""Brand CRUD — the CORE of the manual admin flow.

As the task's suggestion states: manual brand CRUD is core; crawling is optional.
These endpoints are used by the Admin panel. All reads pass through the service
so that embedding documents are never exposed across brands.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.brand import Brand
from app.models.audit_log import AuditLog
from app.schemas.schemas import BrandCreate, BrandOut, BrandUpdate
from app.services.vector_store import delete_all_for_brand
from app.services.brand_detect import detect_brand

router = APIRouter()


@router.get("", response_model=list[BrandOut])
def list_brands(db: Session = Depends(get_db)):
    return db.query(Brand).order_by(Brand.name).all()


@router.post("", response_model=BrandOut, status_code=201)
def create_brand(payload: BrandCreate, db: Session = Depends(get_db)):
    existing = db.query(Brand).filter(Brand.name == payload.name.strip()).first()
    if existing:
        raise HTTPException(409, "A brand with this name already exists")
    brand = Brand(
        name=payload.name.strip(),
        description=payload.description,
        website_url=payload.website_url,
    )
    db.add(brand)
    db.add(AuditLog(actor_user_id="agent", entity_type="brand", action="create", detail=brand.name))
    db.commit()
    db.refresh(brand)
    return brand


@router.get("/detect", response_model=dict)
def detect(query: str, db: Session = Depends(get_db)):
    brands = [b.name for b in db.query(Brand).all()]
    return {"brand": detect_brand(brands, query)}


@router.get("/{brand_id}", response_model=BrandOut)
def get_brand(brand_id: str, db: Session = Depends(get_db)):
    brand = db.get(Brand, brand_id)
    if not brand:
        raise HTTPException(404, "Brand not found")
    return brand


@router.patch("/{brand_id}", response_model=BrandOut)
def update_brand(brand_id: str, payload: BrandUpdate, db: Session = Depends(get_db)):
    brand = db.get(Brand, brand_id)
    if not brand:
        raise HTTPException(404, "Brand not found")
    data = payload.dict(exclude_unset=True)
    if "name" in data and data["name"]:
        clash = db.query(Brand).filter(Brand.name == data["name"].strip(), Brand.id != brand_id).first()
        if clash:
            raise HTTPException(409, "A brand with this name already exists")
        data["name"] = data["name"].strip()
    for k, v in data.items():
        setattr(brand, k, v)
    db.commit()
    db.refresh(brand)
    return brand


@router.delete("/{brand_id}", status_code=204)
def delete_brand(brand_id: str, db: Session = Depends(get_db)):
    brand = db.get(Brand, brand_id)
    if not brand:
        raise HTTPException(404, "Brand not found")
    delete_all_for_brand(brand.name)
    db.delete(brand)
    db.commit()
    return None


@router.get("/detect", response_model=dict)
def detect(query: str, db: Session = Depends(get_db)):
    brands = [b.name for b in db.query(Brand).all()]
    return {"brand": detect_brand(brands, query)}