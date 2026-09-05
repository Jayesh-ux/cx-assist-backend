"""audit_logs: immutable record of who did what, when (review decisions, CRUD, sends)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String, Text

from app.db.base_class import Base


def gen_id() -> str:
    return str(uuid.uuid4())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=gen_id)
    actor_user_id = Column(String(36), nullable=True)
    entity_type = Column(String(48), default="", index=True)  # brand|message|source|auth|...
    entity_id = Column(String(36), default="", index=True)
    action = Column(String(48), default="")
    detail = Column(Text, default="")
    request_id = Column(String(64), default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "actor_user_id": self.actor_user_id, "entity_type": self.entity_type,
            "entity_id": self.entity_id, "action": self.action, "detail": self.detail or "",
            "request_id": self.request_id, "created_at": self.created_at.isoformat() if self.created_at else None,
        }