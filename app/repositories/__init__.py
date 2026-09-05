"""Repository pattern: centralise data access for each aggregate so routers
depend on an interface rather than raw SQLAlchemy. Each repo wraps a Session."""
from __future__ import annotations

from typing import Sequence

from sqlalchemy.orm import Session

from app.models.brand import Brand
from app.models.brand_source import BrandSource
from app.models.conversation import Conversation
from app.models.customer import Customer
from app.models.knowledge_base import KnowledgeBase
from app.models.message import Message
from app.models.order import Order
from app.models.audit_log import AuditLog
from app.models.user import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, user: User) -> User:
        self._db.add(user)
        self._db.flush()
        return user

    def get_by_email(self, email: str) -> User | None:
        return self._db.query(User).filter(User.email == email).first()

    def get(self, user_id: str) -> User | None:
        return self._db.get(User, user_id)


class BrandRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, brand: Brand) -> Brand:
        self._db.add(brand)
        self._db.flush()
        return brand

    def get(self, brand_id: str) -> Brand | None:
        return self._db.get(Brand, brand_id)

    def get_by_name(self, name: str) -> Brand | None:
        return self._db.query(Brand).filter(Brand.name == name).first()

    def list(self) -> Sequence[Brand]:
        return self._db.query(Brand).order_by(Brand.created_at).all()

    def delete(self, brand_id: str) -> bool:
        b = self.get(brand_id)
        if not b:
            return False
        self._db.delete(b)
        self._db.flush()
        return True


class SourceRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, source: BrandSource) -> BrandSource:
        self._db.add(source)
        self._db.flush()
        return source

    def get(self, source_id: str) -> BrandSource | None:
        return self._db.get(BrandSource, source_id)

    def list_by_brand(self, brand_id: str) -> Sequence[BrandSource]:
        return self._db.query(BrandSource).filter(
            BrandSource.brand_id == brand_id).order_by(BrandSource.created_at).all()


class KnowledgeRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, kb: KnowledgeBase) -> KnowledgeBase:
        self._db.add(kb)
        self._db.flush()
        return kb

    def get(self, kb_id: str) -> KnowledgeBase | None:
        return self._db.get(KnowledgeBase, kb_id)

    def list_by_brand(self, brand_id: str) -> Sequence[KnowledgeBase]:
        return self._db.query(KnowledgeBase).filter(
            KnowledgeBase.brand_id == brand_id).order_by(KnowledgeBase.created_at).all()

    def list_by_filter(self, brand_id: str, policy_type: str | None) -> Sequence[KnowledgeBase]:
        q = self._db.query(KnowledgeBase).filter(KnowledgeBase.brand_id == brand_id)
        if policy_type:
            q = q.filter(KnowledgeBase.policy_type == policy_type)
        return q.order_by(KnowledgeBase.created_at).all()

    def delete(self, kb_id: str) -> bool:
        k = self.get(kb_id)
        if not k:
            return False
        self._db.delete(k)
        self._db.flush()
        return True

    def delete_by_brand(self, brand_id: str) -> None:
        self._db.query(KnowledgeBase).filter(KnowledgeBase.brand_id == brand_id).delete()
        self._db.flush()


class ConversationRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, conv: Conversation) -> Conversation:
        self._db.add(conv)
        self._db.flush()
        return conv

    def get(self, conv_id: str) -> Conversation | None:
        return self._db.get(Conversation, conv_id)

    def list(self, limit: int = 50) -> Sequence[Conversation]:
        return self._db.query(Conversation).order_by(Conversation.updated_at.desc()).limit(limit).all()


class MessageRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, msg: Message) -> Message:
        self._db.add(msg)
        self._db.flush()
        return msg

    def list_by_conversation(self, conv_id: str) -> Sequence[Message]:
        return self._db.query(Message).filter(
            Message.conversation_id == conv_id).order_by(Message.created_at).all()


class OrderRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, order: Order) -> Order:
        self._db.add(order)
        self._db.flush()
        return order


class AuditRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def log(self, actor_user_id: str | None, entity_type: str, entity_id: str,
            action: str, detail: str = "", request_id: str = "") -> AuditLog:
        rec = AuditLog(actor_user_id=actor_user_id, entity_type=entity_type,
                       entity_id=entity_id, action=action, detail=detail,
                       request_id=request_id)
        self._db.add(rec)
        return rec

    def list(self, limit: int = 100) -> Sequence[AuditLog]:
        return self._db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()