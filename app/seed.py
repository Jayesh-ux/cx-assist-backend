"""Seed a couple of demo brands + brand-isolated knowledge so the app is useful
out of the box (and to demonstrate the manual-BRAND-CRUD-as-core design)."""
from __future__ import annotations

from app.db.session import SessionLocal
from app.models.brand import Brand
from app.services import vector_store
from app.services.chunker import chunk_text

DEMO = [
    {
        "name": "Acme Telecom",
        "description": "Telecom & broadband provider",
        "website_url": "https://acme.example.com",
        "knowledge": [
            "Acme Telecom allows returns within 30 days of purchase. Devices must be in original packaging and unused to qualify for a refund.",
            "Our broadband plans include free installation and a monthly data rollover of up to 200GB for active customers.",
            "To cancel a plan, contact support at least 3 days before your billing cycle ends. Early termination fees may apply.",
            "Acme Telecom replaces defective hardware under warranty for up to 12 months from the date of purchase.",
        ],
    },
    {
        "name": "Globex Bank",
        "description": "Retail & business banking",
        "website_url": "https://globex.example.com",
        "knowledge": [
            "Globex Bank customers can dispute a transaction within 60 days of the charge appearing on their statement.",
            "Our savings accounts pay an interest rate of 4.5% per annum and have no minimum balance requirement.",
            "To report a lost or stolen card, call 24/7 support immediately; liability is limited to Rs 0 once reported.",
            "Globex Bank routing numbers are available inside the mobile app under Account Details.",
        ],
    },
]


def main() -> None:
    db = SessionLocal()
    try:
        for item in DEMO:
            existing = db.query(Brand).filter(Brand.name == item["name"]).first()
            if existing:
                continue
            brand = Brand(name=item["name"], description=item["description"], website_url=item["website_url"])
            db.add(brand)
            db.commit()
            db.refresh(brand)
            chunks = []
            for text in item["knowledge"]:
                chunks.extend(chunk_text(text, size=400, overlap=40))
            vector_store.ensure_collection()
            vector_store.upsert_chunks(brand=brand.name, chunks=chunks, source="seed")
            print(f"seeded brand {brand.name} with {len(chunks)} chunks")
    finally:
        db.close()


if __name__ == "__main__":
    main()