"""Unit tests for core services: embeddings, document processor, transcription."""
import uuid
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

pytestmark = pytest.mark.asyncio


class TestEmbeddingService:
    def test_embed_texts_returns_correct_dimension(self):
        from app.services.embeddings import embed_texts
        with patch("app.services.embeddings._get_model") as mock:
            model = MagicMock()
            model.encode.return_value = np.random.rand(2, 384).astype(np.float32)
            mock.return_value = model
            result = embed_texts(["hello world", "second text"])
        assert len(result) == 2
        assert len(result[0]) == 384

    def test_embed_query_single(self):
        from app.services.embeddings import embed_query
        with patch("app.services.embeddings._get_model") as mock:
            model = MagicMock()
            model.encode.return_value = np.random.rand(1, 384).astype(np.float32)
            mock.return_value = model
            result = embed_query("test query")
        assert len(result) == 384

    def test_cosine_similarity_identical(self):
        from app.services.embeddings import cosine_similarity
        v = [0.1] * 384
        assert abs(cosine_similarity(v, v) - 1.0) < 1e-5

    def test_cosine_similarity_zero_vector(self):
        from app.services.embeddings import cosine_similarity
        a = [0.0] * 384
        b = [0.1] * 384
        assert cosine_similarity(a, b) == 0.0


class TestDocumentProcessor:
    def test_extract_pdf_text_pymupdf(self):
        from app.services.document_processor import _extract_pdf_text
        import fitz
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Hello PDF World")
        pdf_bytes = doc.tobytes()
        text = _extract_pdf_text(pdf_bytes)
        assert "Hello PDF World" in text

    def test_chunks_from_text(self):
        from app.services.document_processor import _chunks_from_text
        long_text = "A" * 5000
        chunks = _chunks_from_text(long_text)
        assert len(chunks) > 1
        for c in chunks:
            assert c["start_time"] is None
            assert c["end_time"] is None

    def test_chunks_from_segments(self):
        from app.services.document_processor import _chunks_from_segments
        from app.services.transcription import TranscriptSegment
        segs = [
            TranscriptSegment(text=f"Word{i} " * 80, start=float(i * 5), end=float(i * 5 + 4))
            for i in range(5)
        ]
        chunks = _chunks_from_segments(segs)
        assert len(chunks) >= 1
        for c in chunks:
            assert c["start_time"] is not None
            assert c["end_time"] is not None

    async def test_process_document_pdf_success(self, db, test_document):
        from app.services.document_processor import process_document

        fake_pdf = b"%PDF-1.4 test content"

        with patch("app.services.document_processor._extract_pdf_text", return_value="Hello world " * 200), \
             patch("app.services.embeddings.embed_texts", return_value=[[0.1] * 384] * 5):
            await process_document(db, test_document, fake_pdf)

        await db.refresh(test_document)
        assert test_document.status == "ready"

    async def test_process_document_error_handling(self, db, test_document):
        from app.services.document_processor import process_document

        with patch("app.services.document_processor._extract_pdf_text", side_effect=Exception("PDF parse error")):
            await process_document(db, test_document, b"bad pdf bytes")

        await db.refresh(test_document)
        assert test_document.status == "error"
        assert "PDF parse error" in test_document.error_message


class TestSecurityUtils:
    def test_password_hash_and_verify(self):
        from app.core.security import get_password_hash, verify_password
        hashed = get_password_hash("mypassword")
        assert verify_password("mypassword", hashed)
        assert not verify_password("wrongpassword", hashed)

    def test_create_and_decode_token(self):
        from app.core.security import create_access_token, decode_access_token
        token = create_access_token({"sub": "user-123"})
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "user-123"

    def test_decode_invalid_token(self):
        from app.core.security import decode_access_token
        result = decode_access_token("this.is.invalid")
        assert result is None
