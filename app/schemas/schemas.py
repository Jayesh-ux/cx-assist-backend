from __future__ import annotations

from pydantic import BaseModel, Field


class BrandCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    website_url: str = ""


class BrandUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    website_url: str | None = None
    is_active: bool | None = None


class BrandOut(BaseModel):
    id: str
    name: str
    description: str = ""
    website_url: str = ""
    is_active: bool = True

    class Config:
        from_attributes = True


class ConversationCreate(BaseModel):
    brand_id: str
    customer_message: str = Field(min_length=1)


class GenerateReply(BaseModel):
    brand_id: str
    customer_message: str = Field(min_length=1)


class ReviewDecision(BaseModel):
    action: str = Field(..., pattern="^(approve|edit|regenerate|manual|send)$")
    final_text: str | None = None
    human_note: str = ""


class ManualReplyCreate(BaseModel):
    brand_id: str
    conversation_id: str
    text: str = Field(min_length=1)
    human_note: str = ""


class IngestRequest(BaseModel):
    brand_id: str
    source: str = "manual"
    chunks: list[str] = []


class CrawlRequest(BaseModel):
    brand_id: str
    url: str = Field(min_length=4)


class SearchRequest(BaseModel):
    brand_id: str
    query: str = Field(min_length=1)
    top_k: int = 5


# --- Auth ---
class UserCreate(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=6)
    full_name: str = ""
    role: str = "agent"  # admin | agent


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str = ""
    role: str = "agent"
    is_active: bool = True

    class Config:
        from_attributes = True


# --- Knowledge base (manual CRUD) ---
class KBChunkCreate(BaseModel):
    brand_id: str
    policy_type: str = "faq"
    title: str = ""
    source_url: str = ""
    content: str = Field(min_length=1)


class KBUpdate(BaseModel):
    policy_type: str | None = None
    title: str | None = None
    source_url: str | None = None
    content: str | None = None


class OrderLookup(BaseModel):
    brand_id: str
    order_number: str = Field(min_length=1)


class ConversationCreateNew(BaseModel):
    brand_id: str
    customer_message: str = Field(min_length=1)
    customer_email: str = ""