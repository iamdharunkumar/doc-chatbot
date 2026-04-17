"""Chat routes: create session, stream answer, history."""
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.api.deps import CurrentUser, DB
from app.models.chat import ChatMessage, ChatSession
from app.models.document import Document
from app.schemas.chat import ChatHistoryOut, ChatRequest, ChatSessionOut
from app.services import llm

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/{doc_id}/stream")
async def chat_stream(
    doc_id: uuid.UUID,
    body: ChatRequest,
    current_user: CurrentUser,
    db: DB,
):
    """SSE streaming endpoint. Returns text/event-stream."""
    doc = await _get_doc(db, doc_id, current_user.id)

    # Resolve or create session
    session: ChatSession
    if body.session_id:
        result = await db.execute(
            select(ChatSession).where(
                ChatSession.id == body.session_id,
                ChatSession.user_id == current_user.id,
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
    else:
        session = ChatSession(
            user_id=current_user.id,
            document_id=doc_id,
            title=body.question[:60],
        )
        db.add(session)
        await db.flush()
        await db.refresh(session)

    # Persist user message
    user_msg = ChatMessage(
        session_id=session.id, role="user", content=body.question
    )
    db.add(user_msg)
    await db.commit()

    # Build history for context (last 6 messages)
    hist_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(6)
    )
    history = [{"role": m.role, "content": m.content} for m in reversed(hist_result.scalars().all())]

    async def event_generator() -> AsyncGenerator[str, None]:
        full = ""
        # First chunk: send session id so client can track
        yield f"data: {{\"session_id\": \"{session.id}\"}}\n\n"

        async for token in llm.stream_answer(db, doc_id, body.question, history):
            full += token
            # Escape newlines inside SSE data
            safe = token.replace("\n", "\\n")
            yield f"data: {safe}\n\n"

        # Store assistant reply
        assistant_msg = ChatMessage(
            session_id=session.id, role="assistant", content=full
        )
        db.add(assistant_msg)
        await db.commit()

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{doc_id}/sessions", response_model=list[ChatSessionOut])
async def list_sessions(doc_id: uuid.UUID, current_user: CurrentUser, db: DB):
    await _get_doc(db, doc_id, current_user.id)
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.document_id == doc_id, ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
    )
    return result.scalars().all()


@router.get("/sessions/{session_id}/history", response_model=ChatHistoryOut)
async def session_history(session_id: uuid.UUID, current_user: CurrentUser, db: DB):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id, ChatSession.user_id == current_user.id
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    msg_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    return ChatHistoryOut(session=session, messages=msg_result.scalars().all())


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: uuid.UUID, current_user: CurrentUser, db: DB):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id, ChatSession.user_id == current_user.id
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.delete(session)


# ── helpers ──────────────────────────────────────────────────────────────────

async def _get_doc(db, doc_id: uuid.UUID, user_id: uuid.UUID) -> Document:
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.owner_id == user_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.status != "ready":
        raise HTTPException(
            status_code=400, detail=f"Document not ready (status: {doc.status})"
        )
    return doc
