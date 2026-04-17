import uuid
from datetime import datetime
from pydantic import BaseModel


class ChatSessionCreate(BaseModel):
    document_id: uuid.UUID
    title: str = "New Chat"


class ChatSessionOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    document_id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    question: str
    session_id: uuid.UUID | None = None  # create new if None


class ChatHistoryOut(BaseModel):
    session: ChatSessionOut
    messages: list[MessageOut]
