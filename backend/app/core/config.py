from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Literal
import os
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


class Settings(BaseSettings):
    # Search for .env in current, parent, or grandparent directories
    model_config = SettingsConfigDict(
        env_file=[".env", "../.env", "../../.env", "../../../.env", "../../../../.env"],
        extra="ignore"
    )

    # App
    APP_NAME: str = "DocChatbot API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: Literal["development", "production", "test"] = "development"

    # Security / JWT
    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION_USE_STRONG_SECRET"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/docchatbot"
    DATABASE_SSL: bool = False
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL: int = 300  # 5 minutes

    # Storage (Compatible with MinIO, AWS S3, and Cloudflare R2)
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "doc-chatbot"
    MINIO_SECURE: bool = False
    MINIO_REGION: str = "us-east-1"

    # Groq LLM
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 2048

    # Whisper
    WHISPER_MODEL: str = "base"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"

    # Embeddings
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200

    # Rate limiting
    RATE_LIMIT: str = "30/minute"

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:3001"]


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    # Auto-fix DATABASE_URL to use asyncpg if it's a standard postgres url
    if s.DATABASE_URL.startswith("postgresql://"):
        s.DATABASE_URL = s.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

    # Normalize SSL query parameters and keep SSL intent in a dedicated boolean.
    valid_sslmodes = {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}
    ssl_enabled = s.DATABASE_SSL
    parts = urlsplit(s.DATABASE_URL)
    if parts.query:
        query_items = parse_qsl(parts.query, keep_blank_values=True)
        normalized_items: list[tuple[str, str]] = []
        for key, value in query_items:
            if key in {"ssl", "channel_binding"}:
                if key == "ssl":
                    lowered = value.strip().lower()
                    ssl_enabled = lowered not in {"false", "0", "no", "off"}
                continue
            if key == "sslmode":
                lowered = value.strip().lower()
                if lowered in {"true", "1", "yes", "on"}:
                    value = "require"
                elif lowered in {"false", "0", "no", "off"}:
                    value = "disable"
                elif lowered not in valid_sslmodes:
                    value = "require"
                else:
                    value = lowered
                ssl_enabled = value != "disable"
                continue
            normalized_items.append((key, value))
        s.DATABASE_URL = urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(normalized_items), parts.fragment)
        )
    s.DATABASE_SSL = ssl_enabled
    return s


settings = get_settings()
