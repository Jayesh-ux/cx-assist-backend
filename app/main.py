"""CX Assist — Application entrypoint. Wire the FastAPI app, routers, lifespan bootstrap."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (admin, auth, brands, conversations, health, knowledge,
                     orders, replies, review, search)
from app.core.config import settings
from app.core.logging import logger
from app.core.request_id import RequestIDMiddleware
from app.db.session import engine
from app.workers.jobs import worker_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: ensure tables/collections + start the background job worker."""
    from app.db import base  # noqa: F401  (ensure models are imported for metadata)
    from app.db.base import Base
    logger.info("CX Assist starting up")

    # Fresh deployments (Render uses plain `uvicorn`, no Alembic run) rely on
    # create_all to materialise the schema on first boot. Run it in a background
    # task so a slow-to-wake database (free-tier Postgres) never blocks boot.
    async def ensure_schema():
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("create_all: tables ensured")
        except Exception as e:  # noqa: BLE001  — keep serving /health even if DB is down
            logger.error("create_all failed: %s", e)
        try:
            from app.services.vector_store import ensure_collection
            ensure_collection()
        except Exception as e:  # noqa: BLE001
            logger.error("ensure_collection failed: %s", e)

    schema_task = asyncio.create_task(ensure_schema())
    stop_event = asyncio.Event()
    worker_task = asyncio.create_task(worker_loop(stop_event))
    app.state.worker_stop = stop_event
    app.state.worker_task = worker_task
    app.state.schema_task = schema_task
    yield
    stop_event.set()
    worker_task.cancel()
    schema_task.cancel()
    logger.info("CX Assist shutting down")
    engine.dispose()


app = FastAPI(
    title="CX Assist",
    version="1.1.0",
    description="Production-grade AI-powered CX reply assistant with strict no-hallucination guardrails.",
    lifespan=lifespan,
)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(brands.router, prefix="/api/brands", tags=["brands"])
app.include_router(conversations.router, prefix="/api/conversations", tags=["conversations"])
app.include_router(replies.router, prefix="/api/replies", tags=["replies"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(review.router, prefix="/api/review", tags=["review"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["knowledge base"])
app.include_router(orders.router, prefix="/api/orders", tags=["orders"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])


@app.get("/", include_in_schema=False)
def root():
    return {"service": "CX Assist", "docs": "/docs", "status": "running"}