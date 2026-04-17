"""
Shared pytest fixtures for the entire test suite.
Uses an in-memory SQLite-compatible approach via async PostgreSQL test DB.
"""
import asyncio
import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import create_access_token, get_password_hash
from app.main import app
from app.models.user import User
from app.models.document import Document, DocumentChunk

# ── Test DB ───────────────────────────────────────────────────────────────────

TEST_DATABASE_URL = settings.DATABASE_URL.replace("/docchatbot", "/docchatbot_test") if "docchatbot" in settings.DATABASE_URL else settings.DATABASE_URL

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    """Create all tables once for the test session."""
    async with test_engine.begin() as conn:
        try:
            await conn.execute(__import__("sqlalchemy").text("CREATE EXTENSION IF NOT EXISTS vector"))
        except Exception:
            pass
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture()
async def db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture()
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


# ── Test users ────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture()
async def test_user(db: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"test-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Test User",
        hashed_password=get_password_hash("testpass123"),
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture()
def auth_headers(test_user: User) -> dict:
    token = create_access_token({"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}


# ── Test documents ────────────────────────────────────────────────────────────

@pytest_asyncio.fixture()
async def test_document(db: AsyncSession, test_user: User) -> Document:
    doc = Document(
        id=uuid.uuid4(),
        owner_id=test_user.id,
        filename=f"{test_user.id}/test.pdf",
        original_filename="test.pdf",
        file_type="pdf",
        file_size=1024,
        storage_path=f"{test_user.id}/test.pdf",
        status="ready",
        summary="A test document summary.",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


@pytest_asyncio.fixture()
async def test_audio_document(db: AsyncSession, test_user: User) -> Document:
    doc = Document(
        id=uuid.uuid4(),
        owner_id=test_user.id,
        filename=f"{test_user.id}/test.mp3",
        original_filename="test.mp3",
        file_type="audio",
        file_size=2048,
        storage_path=f"{test_user.id}/test.mp3",
        status="ready",
        duration_seconds=120.0,
    )
    db.add(doc)
    # Add chunks with timestamps
    chunks = [
        DocumentChunk(
            id=uuid.uuid4(),
            document_id=doc.id,
            content=f"Audio segment {i} content with some words about topic {i}.",
            chunk_index=i,
            start_time=float(i * 10),
            end_time=float(i * 10 + 9),
            embedding=[0.1 * (i + 1)] * 384,
        )
        for i in range(3)
    ]
    db.add_all(chunks)
    await db.commit()
    await db.refresh(doc)
    return doc


# ── Mocks ─────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def mock_redis(monkeypatch):
    """Mock Redis so tests don't need a running Redis server."""
    with patch("app.core.cache.get_redis") as mock:
        redis_mock = AsyncMock()
        redis_mock.get = AsyncMock(return_value=None)
        redis_mock.setex = AsyncMock(return_value=True)
        redis_mock.delete = AsyncMock(return_value=1)
        redis_mock.keys = AsyncMock(return_value=[])
        mock.return_value = redis_mock
        yield mock


@pytest.fixture(autouse=True)
def mock_minio(monkeypatch):
    """Mock MinIO storage so tests don't need a running MinIO server."""
    with patch("app.core.storage._get_client") as mock:
        client = MagicMock()
        client.bucket_exists.return_value = True
        client.put_object.return_value = None
        client.get_object.return_value = MagicMock(
            read=MagicMock(return_value=b"fake-file-bytes"),
            close=MagicMock(),
            release_conn=MagicMock(),
        )
        client.remove_object.return_value = None
        client.presigned_get_object.return_value = "http://minio/presigned-url"
        mock.return_value = client
        yield mock
