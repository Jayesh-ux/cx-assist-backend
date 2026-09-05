"""Knowledge base: manual CRUD (core flow) and brand_sources registry + optional crawl trigger."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.brand import Brand
from app.models.brand_source import BrandSource
from app.models.knowledge_base import KnowledgeBase
from app.schemas.schemas import CrawlRequest, KBChunkCreate, KBUpdate
from app.services import vector_store
from app.services.chunker import chunk_documents
from app.services.crawler import crawl_and_index

router = APIRouter()


def _brand_or_404(db: Session, brand_id: str) -> Brand:
    b = db.get(Brand, brand_id)
    if not b:
        raise HTTPException(404, "Brand not found")
    return b


@router.post("/chunks", status_code=201)
def ingest_chunks(payload: KBChunkCreate, db: Session = Depends(get_db)):
    """Manual CRUD: index a single policy chunk for a brand (upsert into vector scope)."""
    brand = _brand_or_404(db, payload.brand_id)
    source = payload.source_url or "manual"
    count = vector_store.upsert_chunks(brand=brand.name, chunks=[payload.content], source=source)
    return {"indexed": count, "brand": brand.name, "source": source, "policy_type": payload.policy_type}


@router.post("/documents", status_code=201)
def ingest_document(payload: KBChunkCreate, db: Session = Depends(get_db)):
    """Store a KB record AND index its chunk for the brand (keeps DB + vector in sync)."""
    brand = _brand_or_404(db, payload.brand_id)
    kb = KnowledgeBase(
        brand_id=brand.id, policy_type=payload.policy_type, title=payload.title,
        source_url=payload.source_url, content=payload.content, chunk=payload.content,
    )
    db.add(kb)
    db.flush()
    count = vector_store.upsert_chunks(brand=brand.name, chunks=[payload.content],
                                       source=payload.source_url or "manual")
    kb.embedding_id = "indexed"
    db.commit()
    return {"id": kb.id, "indexed": count, "brand": brand.name}


@router.get("/brand/{brand_id}")
def list_kb(brand_id: str, policy_type: str | None = None, db: Session = Depends(get_db)):
    _brand_or_404(db, brand_id)
    q = db.query(KnowledgeBase).filter(KnowledgeBase.brand_id == brand_id)
    if policy_type:
        q = q.filter(KnowledgeBase.policy_type == policy_type)
    return [k.to_dict() for k in q.order_by(KnowledgeBase.created_at.desc()).limit(200).all()]


@router.get("/brand/{brand_id}/sources")
def list_sources(brand_id: str, db: Session = Depends(get_db)):
    _brand_or_404(db, brand_id)
    return [s.to_dict() for s in db.query(BrandSource).filter(BrandSource.brand_id == brand_id)
            .order_by(BrandSource.created_at.desc()).all()]


@router.patch("/documents/{kb_id}")
def update_kb(kb_id: str, payload: KBUpdate, db: Session = Depends(get_db)):
    kb = db.get(KnowledgeBase, kb_id)
    if not kb:
        raise HTTPException(404, "Knowledge document not found")
    data = payload.dict(exclude_unset=True)
    if "content" in data and data["content"]:
        data["chunk"] = data["content"]
        data["content"] = data["content"]
    for k, v in data.items():
        setattr(kb, k, v)
    db.commit()
    db.refresh(kb)
    return kb.to_dict()


@router.delete("/documents/{kb_id}", status_code=204)
def delete_kb(kb_id: str, db: Session = Depends(get_db)):
    kb = db.get(KnowledgeBase, kb_id)
    if not kb:
        raise HTTPException(404, "Knowledge document not found")
    # best-effort remove from vector store
    try:
        vector_store.delete_all_for_brand(db.get(Brand, kb.brand_id).name)
    except Exception:
        pass
    db.delete(kb)
    db.commit()
    return None


@router.post("/crawl", status_code=202)
def ingest_crawl(payload: CrawlRequest, background: BackgroundTasks, db: Session = Depends(get_db)):
    """OPTIONAL: crawl + clean + chunk + index a brand website asynchronously."""
    brand = _brand_or_404(db, payload.brand_id)
    src = BrandSource(brand_id=brand.id, source_url=payload.url, policy_type="unknown", status="pending")
    db.add(src)
    db.commit()
    db.refresh(src)
    background.add_task(crawl_and_index, brand.name, payload.url, src.id)
    return {"status": "started", "brand": brand.name, "url": payload.url, "source_id": src.id}