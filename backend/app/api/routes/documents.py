"""Document upload, list, retrieve, delete, summarize, timestamps."""
import asyncio
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DB
from app.core import storage
from app.models.document import Document
from app.schemas.document import (
    DocumentListOut,
    DocumentOut,
    SummarizeResponse,
    TimestampResponse,
)
from app.services import document_processor, llm
from app.core.cache import cache_delete

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_MIME: dict[str, str] = {
    "application/pdf": "pdf",
    "audio/mpeg": "audio",
    "audio/mp4": "audio",
    "audio/wav": "audio",
    "audio/x-wav": "audio",
    "audio/ogg": "audio",
    "audio/flac": "audio",
    "audio/aac": "audio",
    "video/mp4": "video",
    "video/x-matroska": "video",
    "video/quicktime": "video",
    "video/webm": "video",
    "video/avi": "video",
    "video/x-msvideo": "video",
}

MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    current_user: CurrentUser,
    db: DB,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    content_type = file.content_type or ""
    file_type = ALLOWED_MIME.get(content_type)

    # Fallback: guess from extension
    if not file_type and file.filename:
        ext = file.filename.rsplit(".", 1)[-1].lower()
        ext_map = {
            "pdf": "pdf", "mp3": "audio", "wav": "audio", "m4a": "audio",
            "ogg": "audio", "flac": "audio", "aac": "audio",
            "mp4": "video", "mkv": "video", "avi": "video", "mov": "video", "webm": "video",
        }
        file_type = ext_map.get(ext)

    if not file_type:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type not supported. Allowed: PDF, audio (mp3/wav/m4a/ogg/flac/aac), video (mp4/mkv/avi/mov/webm)",
        )

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large. Max 500 MB.",
        )

    safe_name = f"{current_user.id}/{uuid.uuid4()}/{file.filename}"

    # Upload to MinIO in thread pool
    await asyncio.get_event_loop().run_in_executor(
        None, storage.upload_file, safe_name, file_bytes, content_type
    )

    doc = Document(
        owner_id=current_user.id,
        filename=safe_name,
        original_filename=file.filename or "unknown",
        file_type=file_type,
        file_size=len(file_bytes),
        storage_path=safe_name,
        status="pending",
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)

    # Process in background
    background_tasks.add_task(
        document_processor.process_document, doc.id, file_bytes
    )

    return doc


@router.get("", response_model=DocumentListOut)
async def list_documents(
    current_user: CurrentUser,
    db: DB,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    total_result = await db.execute(
        select(func.count(Document.id)).where(Document.owner_id == current_user.id)
    )
    total = total_result.scalar_one()

    result = await db.execute(
        select(Document)
        .where(Document.owner_id == current_user.id)
        .order_by(Document.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    docs = result.scalars().all()
    return DocumentListOut(items=list(docs), total=total)


@router.get("/{doc_id}", response_model=DocumentOut)
async def get_document(doc_id: uuid.UUID, current_user: CurrentUser, db: DB):
    doc = await _get_owned_doc(db, doc_id, current_user.id)
    return doc


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(doc_id: uuid.UUID, current_user: CurrentUser, db: DB):
    doc = await _get_owned_doc(db, doc_id, current_user.id)
    # Delete from MinIO
    await asyncio.get_event_loop().run_in_executor(None, storage.delete_file, doc.storage_path)
    await db.delete(doc)
    await cache_delete(f"summary:{doc_id}")


@router.post("/{doc_id}/summarize", response_model=SummarizeResponse)
async def summarize(doc_id: uuid.UUID, current_user: CurrentUser, db: DB):
    doc = await _get_owned_doc(db, doc_id, current_user.id)
    if doc.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document not ready (status: {doc.status})",
        )
    summary = await llm.summarize_document(db, doc)
    # Persist summary
    doc.summary = summary
    return SummarizeResponse(document_id=doc_id, summary=summary)


@router.get("/{doc_id}/timestamps", response_model=TimestampResponse)
async def get_timestamps(
    doc_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
    query: str = Query(..., min_length=1),
    top_k: int = Query(5, ge=1, le=20),
):
    doc = await _get_owned_doc(db, doc_id, current_user.id)
    if doc.file_type not in ("audio", "video"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Timestamps are only available for audio/video documents",
        )
    if doc.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document not ready (status: {doc.status})",
        )
    timestamps = await llm.find_timestamps(db, doc_id, query, top_k=top_k)
    return TimestampResponse(document_id=doc_id, query=query, timestamps=timestamps)


@router.get("/{doc_id}/presigned-url")
async def presigned_url(doc_id: uuid.UUID, current_user: CurrentUser, db: DB):
    doc = await _get_owned_doc(db, doc_id, current_user.id)
    url = await asyncio.get_event_loop().run_in_executor(
        None, storage.get_presigned_url, doc.storage_path
    )
    return {"url": url}


# ── helpers ──────────────────────────────────────────────────────────────────

async def _get_owned_doc(db, doc_id: uuid.UUID, user_id: uuid.UUID) -> Document:
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.owner_id == user_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return doc
