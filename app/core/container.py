"""Lightweight Dependency Injection container (no external DI lib required).

Holds repositories/services wired once at startup and exposes them via
FastAPI's request.state + dependency functions, making the service layer
testable and the composition explicit (a Tech-Lead expectation)."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.repositories import (
    BrandRepository,
    UserRepository,
    SourceRepository,
    KnowledgeRepository,
    ConversationRepository,
    MessageRepository,
    OrderRepository,
    AuditRepository,
)


@dataclass
class Container:
    users: UserRepository
    brands: BrandRepository
    sources: SourceRepository
    knowledge: KnowledgeRepository
    conversations: ConversationRepository
    messages: MessageRepository
    orders: OrderRepository
    audits: AuditRepository

    @classmethod
    def build(cls, db: Session) -> "Container":
        return cls(
            users=UserRepository(db),
            brands=BrandRepository(db),
            sources=SourceRepository(db),
            knowledge=KnowledgeRepository(db),
            conversations=ConversationRepository(db),
            messages=MessageRepository(db),
            orders=OrderRepository(db),
            audits=AuditRepository(db),
        )