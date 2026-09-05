"""Centralised settings via pydantic-settings. Values come from env or .env."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # DB
    database_url: str = "postgresql+psycopg2://cx:cxpass@localhost:5432/cxassist"

    # Vector DB (ChromaDB)
    chroma_host: str = "localhost"
    chroma_port: str = "8001"
    chroma_http: bool = True
    chroma_collection: str = "brand_context"

    # Embeddings
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    # LLM (OmniRoute + Gemini fallback)
    omnipath_api_key: str = ""
    gemini_api_key: str = ""
    llm_provider: str = "auto"  # auto|omniroute|gemini
    llm_model: str = "datastraw-reply-assistant"
    temperature: float = 0.0
    max_tokens: int = 800

    # Retrieval / validation
    chunk_size: int = 900
    chunk_overlap: int = 120
    top_k: int = 5
    score_threshold: float = 0.55
    confidence_threshold: float = 0.60

    # Admin auth
    admin_api_key: str = "change-me"
    access_token_expire_minutes: int = 480
    secret_key: str = "change-me-to-a-long-random-secret"

    # Redis (cache + rate limiting + retry queue)
    redis_url: str = "redis://localhost:6379/0"

    # Rate limiting (requests per minute per key)
    rate_limit_per_minute: int = 120

    # Webhook
    webhook_url: str = ""

    # Security: never allow cross-brand access
    enforce_brand_isolation: bool = True

    @property
    def cors_origins(self) -> list[str]:
        return ["http://localhost:3000", "http://localhost:3001",
                "https://*.vercel.app", "https://cx-frontend.onrender.com"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()