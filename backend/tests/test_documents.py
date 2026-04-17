"""Tests for document management endpoints."""
import io
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestUpload:
    async def test_upload_pdf_success(self, client: AsyncClient, auth_headers):
        pdf_bytes = b"%PDF-1.4 fake pdf content for testing"

        with patch("app.services.document_processor.process_document", new_callable=AsyncMock):
            resp = await client.post(
                "/api/documents/upload",
                headers=auth_headers,
                files={"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["file_type"] == "pdf"
        assert data["original_filename"] == "test.pdf"
        assert data["status"] in ("pending", "processing")

    async def test_upload_audio_success(self, client: AsyncClient, auth_headers):
        with patch("app.services.document_processor.process_document", new_callable=AsyncMock):
            resp = await client.post(
                "/api/documents/upload",
                headers=auth_headers,
                files={"file": ("audio.mp3", io.BytesIO(b"fake-audio"), "audio/mpeg")},
            )
        assert resp.status_code == 201
        assert resp.json()["file_type"] == "audio"

    async def test_upload_video_success(self, client: AsyncClient, auth_headers):
        with patch("app.services.document_processor.process_document", new_callable=AsyncMock):
            resp = await client.post(
                "/api/documents/upload",
                headers=auth_headers,
                files={"file": ("video.mp4", io.BytesIO(b"fake-video"), "video/mp4")},
            )
        assert resp.status_code == 201
        assert resp.json()["file_type"] == "video"

    async def test_upload_unsupported_type(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/documents/upload",
            headers=auth_headers,
            files={"file": ("file.exe", io.BytesIO(b"binary"), "application/octet-stream")},
        )
        assert resp.status_code == 415

    async def test_upload_unauthenticated(self, client: AsyncClient):
        resp = await client.post(
            "/api/documents/upload",
            files={"file": ("test.pdf", io.BytesIO(b"pdf"), "application/pdf")},
        )
        assert resp.status_code == 401


class TestListDocuments:
    async def test_list_empty(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/documents", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    async def test_list_with_doc(self, client: AsyncClient, auth_headers, test_document):
        resp = await client.get("/api/documents", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        ids = [d["id"] for d in data["items"]]
        assert str(test_document.id) in ids

    async def test_list_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/documents")
        assert resp.status_code == 401


class TestGetDocument:
    async def test_get_existing(self, client: AsyncClient, auth_headers, test_document):
        resp = await client.get(f"/api/documents/{test_document.id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == str(test_document.id)

    async def test_get_not_found(self, client: AsyncClient, auth_headers):
        resp = await client.get(f"/api/documents/{uuid.uuid4()}", headers=auth_headers)
        assert resp.status_code == 404

    async def test_get_other_users_doc(self, client: AsyncClient, auth_headers, db):
        """A user cannot access another user's document."""
        from app.core.security import get_password_hash
        from app.models.user import User
        other_user = User(
            email="other@example.com",
            full_name="Other",
            hashed_password=get_password_hash("pass1234"),
        )
        db.add(other_user)
        from app.models.document import Document
        other_doc = Document(
            owner_id=other_user.id,
            filename="other/file.pdf",
            original_filename="file.pdf",
            file_type="pdf",
            file_size=100,
            storage_path="other/file.pdf",
            status="ready",
        )
        db.add(other_doc)
        await db.commit()

        resp = await client.get(f"/api/documents/{other_doc.id}", headers=auth_headers)
        assert resp.status_code == 404


class TestDeleteDocument:
    async def test_delete_success(self, client: AsyncClient, auth_headers, test_document):
        resp = await client.delete(f"/api/documents/{test_document.id}", headers=auth_headers)
        assert resp.status_code == 204

    async def test_delete_not_found(self, client: AsyncClient, auth_headers):
        resp = await client.delete(f"/api/documents/{uuid.uuid4()}", headers=auth_headers)
        assert resp.status_code == 404


class TestSummarize:
    async def test_summarize_ready_doc(self, client: AsyncClient, auth_headers, test_document):
        with patch("app.services.llm.summarize_document", new_callable=AsyncMock) as mock_sum:
            mock_sum.return_value = "This is a test summary."
            resp = await client.post(f"/api/documents/{test_document.id}/summarize", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["summary"] == "This is a test summary."

    async def test_summarize_not_ready(self, client: AsyncClient, auth_headers, db, test_user):
        from app.models.document import Document
        pending_doc = Document(
            owner_id=test_user.id,
            filename="pend.pdf",
            original_filename="pend.pdf",
            file_type="pdf",
            file_size=100,
            storage_path="pend.pdf",
            status="pending",
        )
        db.add(pending_doc)
        await db.commit()
        resp = await client.post(f"/api/documents/{pending_doc.id}/summarize", headers=auth_headers)
        assert resp.status_code == 400


class TestTimestamps:
    async def test_timestamps_audio(self, client: AsyncClient, auth_headers, test_audio_document):
        with patch("app.services.llm.find_timestamps", new_callable=AsyncMock) as mock_ts:
            mock_ts.return_value = [
                MagicMock(start=0.0, end=9.0, text="Topic discussed here", relevance=0.91)
            ]
            resp = await client.get(
                f"/api/documents/{test_audio_document.id}/timestamps",
                headers=auth_headers,
                params={"query": "topic"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "timestamps" in data
        assert data["query"] == "topic"

    async def test_timestamps_pdf_unsupported(self, client: AsyncClient, auth_headers, test_document):
        resp = await client.get(
            f"/api/documents/{test_document.id}/timestamps",
            headers=auth_headers,
            params={"query": "topic"},
        )
        assert resp.status_code == 400
