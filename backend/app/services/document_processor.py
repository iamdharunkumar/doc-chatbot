"""
Document processing pipeline:
  PDF  → extract text → chunk → embed → store chunks
  Audio/Video → transcribe → chunk by segment → embed → store chunks
"""
import logging
import uuid
from io import BytesIO

from langchain.text_splitter import RecursiveCharacterTextSplitter
from sqlalchemy import select
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.document import Document, DocumentChunk
from app.services.embeddings import embed_texts
from app.services.transcription import TranscriptSegment, transcribe_bytes

logger = logging.getLogger(__name__)

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=settings.CHUNK_SIZE,
    chunk_overlap=settings.CHUNK_OVERLAP,
    separators=["\n\n", "\n", ". ", " ", ""],
)


# ── PDF ──────────────────────────────────────────────────────────────────────


def _extract_pdf_text(data: bytes) -> str:
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=BytesIO(data), filetype="pdf")
        return "\n\n".join(page.get_text() for page in doc)
    except Exception as e:
        logger.warning("PyMuPDF failed (%s), falling back to pdfminer", e)
        from pdfminer.high_level import extract_text
        return extract_text(BytesIO(data))


def _chunks_from_text(text: str) -> list[dict]:
    raw_chunks = _splitter.split_text(text)
    return [
        {"content": c, "chunk_index": i, "start_time": None, "end_time": None}
        for i, c in enumerate(raw_chunks)
    ]


# ── Audio / Video ─────────────────────────────────────────────────────────────


def _chunks_from_segments(segments: list[TranscriptSegment]) -> list[dict]:
    """
    Groups whisper segments into ~CHUNK_SIZE character chunks
    while preserving timestamps.
    """
    chunks: list[dict] = []
    buf_text = ""
    buf_start: float | None = None
    buf_end: float | None = None
    idx = 0

    for seg in segments:
        if buf_start is None:
            buf_start = seg.start
        buf_text += " " + seg.text
        buf_end = seg.end

        if len(buf_text) >= settings.CHUNK_SIZE:
            chunks.append(
                {
                    "content": buf_text.strip(),
                    "chunk_index": idx,
                    "start_time": buf_start,
                    "end_time": buf_end,
                }
            )
            idx += 1
            buf_text = ""
            buf_start = None

    if buf_text.strip():
        chunks.append(
            {
                "content": buf_text.strip(),
                "chunk_index": idx,
                "start_time": buf_start,
                "end_time": buf_end,
            }
        )
    return chunks


# ── Main pipeline ─────────────────────────────────────────────────────────────


async def process_document(
    doc_id: uuid.UUID,
    file_bytes: bytes,
) -> None:
    """Called as a background task after upload."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Document).where(Document.id == doc_id))
        document = result.scalar_one_or_none()
        if not document:
            logger.error("Document %s not found in background task", doc_id)
            return

        try:
            logger.info("Processing document: %s (%s)", document.original_filename, document.file_type)
            document.status = "processing"
            await db.commit()

            raw_chunks: list[dict] = []

            if document.file_type == "pdf":
                text = _extract_pdf_text(file_bytes)
                raw_chunks = _chunks_from_text(text)

            elif document.file_type in ("audio", "video"):
                ext_map = {
                    "audio": _guess_audio_ext(document.original_filename),
                    "video": _guess_video_ext(document.original_filename),
                }
                ext = ext_map[document.file_type]
                segments, duration = transcribe_bytes(file_bytes, ext)
                document.duration_seconds = duration
                raw_chunks = _chunks_from_segments(segments)

            else:
                raise ValueError(f"Unsupported file type: {document.file_type}")

            if not raw_chunks:
                raise ValueError("No content could be extracted from the document")

            # Compute embeddings in batch
            logger.info("Generating embeddings for %d chunks...", len(raw_chunks))
            texts = [c["content"] for c in raw_chunks]
            embeddings = embed_texts(texts)

            chunk_objects = [
                DocumentChunk(
                    id=uuid.uuid4(),
                    document_id=document.id,
                    content=c["content"],
                    chunk_index=c["chunk_index"],
                    start_time=c["start_time"],
                    end_time=c["end_time"],
                    embedding=emb,
                )
                for c, emb in zip(raw_chunks, embeddings)
            ]

            db.add_all(chunk_objects)
            document.status = "ready"
            logger.info("Document ready: %s", document.id)

        except Exception as exc:
            logger.exception("Document processing failed for %s", document.id)
            document.status = "error"
            document.error_message = str(exc)

        finally:
            await db.commit()


def _guess_audio_ext(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower()
    return f".{ext}" if ext in {"mp3", "wav", "m4a", "ogg", "flac", "aac"} else ".mp3"


def _guess_video_ext(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower()
    return f".{ext}" if ext in {"mp4", "mkv", "avi", "mov", "webm"} else ".mp4"
