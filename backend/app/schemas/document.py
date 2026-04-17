import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    filename: str
    original_filename: str
    file_type: Literal["pdf", "audio", "video"]
    file_size: int
    status: Literal["pending", "processing", "ready", "error"]
    error_message: str | None = None
    duration_seconds: float | None = None
    summary: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentListOut(BaseModel):
    items: list[DocumentOut]
    total: int


class SummarizeResponse(BaseModel):
    document_id: uuid.UUID
    summary: str


class TimestampEntry(BaseModel):
    start: float      # seconds
    end: float        # seconds
    text: str         # transcript segment text
    relevance: float  # cosine similarity score


class TimestampResponse(BaseModel):
    document_id: uuid.UUID
    query: str
    timestamps: list[TimestampEntry]


class ChunkOut(BaseModel):
    id: uuid.UUID
    content: str
    chunk_index: int
    start_time: float | None = None
    end_time: float | None = None

    model_config = {"from_attributes": True}
