"""Session factory."""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

_connect_args = {"connect_timeout": 10} if settings.database_url.startswith("postgres") else {}

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=False,
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()