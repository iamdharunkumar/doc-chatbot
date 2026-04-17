"""Tests for chat endpoints and services."""
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.models.chat import ChatSession, ChatMessage

pytestmark = pytest.mark.asyncio


class TestChatStream:
    async def test_stream_creates_session(self, client: AsyncClient, auth_headers, test_document):
        async def fake_stream(*args, **kwargs):
            for token in ["Hello", " ", "World"]:
                yield token

        with patch("app.services.llm.stream_answer", side_effect=fake_stream):
            resp = await client.post(
                f"/api/chat/{test_document.id}/stream",
                headers=auth_headers,
                json={"question": "What is this about?"},
            )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")

    async def test_stream_with_existing_session(
        self, client: AsyncClient, auth_headers, test_document, test_user, db
    ):
        session = ChatSession(
            user_id=test_user.id,
            document_id=test_document.id,
            title="Existing Session",
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)

        async def fake_stream(*args, **kwargs):
            yield "Answer"

        with patch("app.services.llm.stream_answer", side_effect=fake_stream):
            resp = await client.post(
                f"/api/chat/{test_document.id}/stream",
                headers=auth_headers,
                json={"question": "Follow up?", "session_id": str(session.id)},
            )
        assert resp.status_code == 200

    async def test_stream_doc_not_found(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            f"/api/chat/{uuid.uuid4()}/stream",
            headers=auth_headers,
            json={"question": "hello"},
        )
        assert resp.status_code == 404

    async def test_stream_unauthenticated(self, client: AsyncClient, test_document):
        resp = await client.post(
            f"/api/chat/{test_document.id}/stream",
            json={"question": "hello"},
        )
        assert resp.status_code == 401


class TestSessionManagement:
    async def test_list_sessions_empty(self, client: AsyncClient, auth_headers, test_document):
        resp = await client.get(f"/api/chat/{test_document.id}/sessions", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_list_sessions_with_data(
        self, client: AsyncClient, auth_headers, test_document, test_user, db
    ):
        session = ChatSession(
            user_id=test_user.id,
            document_id=test_document.id,
            title="My chat",
        )
        db.add(session)
        await db.commit()

        resp = await client.get(f"/api/chat/{test_document.id}/sessions", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_session_history(
        self, client: AsyncClient, auth_headers, test_user, test_document, db
    ):
        session = ChatSession(
            user_id=test_user.id,
            document_id=test_document.id,
            title="History test",
        )
        db.add(session)
        await db.flush()
        msgs = [
            ChatMessage(session_id=session.id, role="user", content="Q1"),
            ChatMessage(session_id=session.id, role="assistant", content="A1"),
        ]
        db.add_all(msgs)
        await db.commit()

        resp = await client.get(
            f"/api/chat/sessions/{session.id}/history", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["messages"]) == 2
        assert data["messages"][0]["role"] == "user"

    async def test_delete_session(
        self, client: AsyncClient, auth_headers, test_user, test_document, db
    ):
        session = ChatSession(
            user_id=test_user.id, document_id=test_document.id, title="Delete me"
        )
        db.add(session)
        await db.commit()

        resp = await client.delete(
            f"/api/chat/sessions/{session.id}", headers=auth_headers
        )
        assert resp.status_code == 204

    async def test_delete_session_not_found(self, client: AsyncClient, auth_headers):
        resp = await client.delete(
            f"/api/chat/sessions/{uuid.uuid4()}", headers=auth_headers
        )
        assert resp.status_code == 404


class TestLLMService:
    """Unit tests for LLM service functions."""

    async def test_find_timestamps_no_chunks(self, db, test_audio_document):
        from app.services.llm import find_timestamps
        # Clear chunks to test empty case
        from sqlalchemy import delete
        from app.models.document import DocumentChunk
        await db.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == test_audio_document.id)
        )
        await db.commit()

        result = await find_timestamps(db, test_audio_document.id, "topic")
        assert result == []

    async def test_summarize_no_chunks(self, db, test_document):
        from app.services.llm import summarize_document
        with patch("app.services.llm._get_llm") as mock_llm:
            mock_instance = AsyncMock()
            mock_instance.ainvoke = AsyncMock(
                return_value=AsyncMock(content="Test summary text.")
            )
            mock_llm.return_value = mock_instance
            result = await summarize_document(db, test_document)
        assert isinstance(result, str)


class TestHealthEndpoint:
    async def test_health(self, client: AsyncClient):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
