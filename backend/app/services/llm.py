"""
LLM service: Groq (Llama 3.1 70B) via LangChain.
Features:
  - Streaming SSE responses
  - Vector similarity search via pgvector
  - LLM response caching in Redis
  - Document summarisation
  - Timestamp extraction for audio/video
"""
import hashlib
import json
import logging
import uuid
from typing import AsyncGenerator

from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage, SystemMessage
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get, cache_set
from app.core.config import settings
from app.models.document import Document, DocumentChunk
from app.schemas.document import TimestampEntry
from app.services.embeddings import embed_query, cosine_similarity

logger = logging.getLogger(__name__)

# ── LLM factory ──────────────────────────────────────────────────────────────


def _get_llm(streaming: bool = False) -> ChatGroq:
    return ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model=settings.GROQ_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        streaming=streaming,
    )


# ── Vector retrieval ─────────────────────────────────────────────────────────

_VECTOR_SEARCH_SQL = text("""
    SELECT id, content, start_time, end_time,
           1 - (embedding <=> CAST(:embedding AS vector)) AS score
    FROM document_chunks
    WHERE document_id = :doc_id
    ORDER BY embedding <=> CAST(:embedding AS vector)
    LIMIT :k
""")


async def retrieve_chunks(
    db: AsyncSession,
    document_id: uuid.UUID,
    query: str,
    k: int = 5,
) -> list[DocumentChunk]:
    query_emb = embed_query(query)
    emb_str = "[" + ",".join(str(x) for x in query_emb) + "]"
    result = await db.execute(
        _VECTOR_SEARCH_SQL,
        {"embedding": emb_str, "doc_id": str(document_id), "k": k},
    )
    rows = result.fetchall()
    chunks = []
    for row in rows:
        c = DocumentChunk()
        c.id = row.id
        c.content = row.content
        c.start_time = row.start_time
        c.end_time = row.end_time
        chunks.append(c)
    return chunks


# ── Prompts ───────────────────────────────────────────────────────────────────

_QA_SYSTEM = """You are a helpful AI assistant that answers questions based ONLY on the provided document context.
If the answer is not in the context, say so honestly — do not hallucinate.
Be concise and precise. Format your response in markdown when helpful."""

_QA_PROMPT = ChatPromptTemplate.from_messages([
    ("system", _QA_SYSTEM),
    ("human", "Context:\n{context}\n\nQuestion: {question}"),
])

_SUMMARY_SYSTEM = """You are an expert document summarizer.
Produce a clear, structured summary of the following document content.
Include key topics, main points, and important details. Use markdown formatting."""

_SUMMARY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", _SUMMARY_SYSTEM),
    ("human", "Document content:\n{content}"),
])


# ── Streaming Chat ────────────────────────────────────────────────────────────

async def stream_answer(
    db: AsyncSession,
    document_id: uuid.UUID,
    question: str,
    history: list[dict] | None = None,
) -> AsyncGenerator[str, None]:
    """
    Retrieve relevant chunks → build prompt → stream LLM response.
    Yields SSE-compatible string chunks.
    """
    chunks = await retrieve_chunks(db, document_id, question, k=6)
    context = "\n\n---\n\n".join(c.content for c in chunks)

    # Build message list including history
    messages = [SystemMessage(content=_QA_SYSTEM)]
    for msg in (history or []):
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        # skip assistant messages in history to keep context window manageable

    # Check cache for non-streaming identical queries
    cache_key = _make_cache_key(document_id, question, context)
    cached = await cache_get(cache_key)
    if cached:
        yield cached["answer"]
        return

    llm = _get_llm(streaming=True)
    prompt_value = _QA_PROMPT.format_messages(context=context, question=question)

    full_answer = ""
    async for chunk in llm.astream(prompt_value):
        token = chunk.content
        full_answer += token
        yield token

    # Store in cache (non-blocking)
    await cache_set(cache_key, {"answer": full_answer}, ttl=settings.CACHE_TTL)


# ── Summarization ─────────────────────────────────────────────────────────────

async def summarize_document(
    db: AsyncSession,
    document: Document,
) -> str:
    cache_key = f"summary:{document.id}"
    cached = await cache_get(cache_key)
    if cached:
        return cached["summary"]

    # Get all chunks ordered by index
    result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document.id)
        .order_by(DocumentChunk.chunk_index)
        .limit(20)  # keep within context window
    )
    chunks = result.scalars().all()
    content = "\n\n".join(c.content for c in chunks)

    if not content.strip():
        return "No content available for summarization."

    llm = _get_llm()
    prompt_value = _SUMMARY_PROMPT.format_messages(content=content[:12000])
    response = await llm.ainvoke(prompt_value)
    summary: str = response.content

    await cache_set(cache_key, {"summary": summary}, ttl=3600)
    return summary


# ── Timestamp extraction ──────────────────────────────────────────────────────

async def find_timestamps(
    db: AsyncSession,
    document_id: uuid.UUID,
    query: str,
    top_k: int = 5,
) -> list[TimestampEntry]:
    """
    Find timestamped segments in audio/video most relevant to the query.
    Only returns segments that have start_time/end_time.
    """
    result = await db.execute(
        select(DocumentChunk)
        .where(
            DocumentChunk.document_id == document_id,
            DocumentChunk.start_time.isnot(None),
        )
    )
    all_chunks = result.scalars().all()

    if not all_chunks:
        return []

    query_emb = embed_query(query)
    scored: list[tuple[float, DocumentChunk]] = []
    for chunk in all_chunks:
        if chunk.embedding:
            score = cosine_similarity(query_emb, chunk.embedding)
            scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_k]

    return [
        TimestampEntry(
            start=c.start_time,
            end=c.end_time,
            text=c.content,
            relevance=round(score, 4),
        )
        for score, c in top
        if score > 0.3  # filter out low-relevance chunks
    ]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_cache_key(doc_id: uuid.UUID, question: str, context: str) -> str:
    payload = f"{doc_id}:{question}:{context[:500]}"
    return "llm:" + hashlib.sha256(payload.encode()).hexdigest()
