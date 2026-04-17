# DocChat AI 🤖

> AI-Powered Document & Multimedia Q&A Web Application

[![CI/CD](https://github.com/your-org/doc-chatbot/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/doc-chatbot/actions)
[![codecov](https://codecov.io/gh/your-org/doc-chatbot/branch/main/graph/badge.svg)](https://codecov.io/gh/your-org/doc-chatbot)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 📄 **PDF Q&A** | Upload PDFs, ask natural-language questions with semantic retrieval |
| 🎵 **Audio Transcription** | Auto-transcribed with faster-whisper (word-level timestamps) |
| 🎬 **Video Analysis** | Video transcription + in-app player with jump-to-timestamp |
| 🤖 **Streaming Chat** | Real-time SSE streaming via Llama 3.1 70B on Groq |
| 🔍 **Vector Search** | pgvector semantic search (FAISS-compatible cosine similarity) |
| 📝 **Auto Summarization** | One-click AI document summary |
| 🔐 **JWT Auth** | Register / login / protected routes |
| ⚡ **Redis Caching** | LLM response caching + rate limiting (30 req/min) |
| 🗄️ **MinIO Storage** | S3-compatible local storage for all uploads |
| 🐳 **Docker Compose** | 5-service production setup |
| 🧪 **95%+ Test Coverage** | pytest + httpx async tests |

---

## 🏗️ Architecture

```
Frontend (Next.js 16)  ──►  Backend (FastAPI)  ──►  PostgreSQL + pgvector
        │                         │                         │
        │                       Redis                  (embeddings)
        │                         │
        │                       MinIO  ◄────  PDF / Audio / Video files
        │                         │
        └────────── SSE Stream ◄──┘
                  (Groq Llama 3.1 70B)
```

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- [Groq API key](https://console.groq.com) (free tier: 14,400 req/day)

### 1. Clone & configure
```bash
git clone https://github.com/your-org/doc-chatbot
cd doc-chatbot
cp .env.example .env
# Edit .env and set GROQ_API_KEY
```

### 2. Start all services
```bash
docker compose up --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Swagger Docs | http://localhost:8000/api/docs |
| MinIO Console | http://localhost:9001 |

---

## 🛠️ Local Development

### Backend
```bash
cd backend

# Create virtual environment
python -m venv .venv && source .venv/bin/activate

# Install dependencies
pip install ".[dev]"

# Start local services (Postgres + Redis + MinIO)
docker compose up db redis minio -d

# Copy & configure .env
cp ../.env.example .env  # then set DATABASE_URL, REDIS_URL, etc.

# Run development server
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
# In project root
bun install   # or: npm install

# Set env
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local

# Start dev server
bun dev   # or: npm run dev
```

---

## 📡 API Reference

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/register` | Create a new user account |
| `POST` | `/api/auth/login` | Get JWT access token |
| `GET`  | `/api/auth/me` | Get current user profile |

### Documents
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/documents/upload` | Upload PDF / audio / video |
| `GET`  | `/api/documents` | List all documents (paginated) |
| `GET`  | `/api/documents/{id}` | Get document details |
| `DELETE` | `/api/documents/{id}` | Delete document |
| `POST` | `/api/documents/{id}/summarize` | Generate AI summary |
| `GET`  | `/api/documents/{id}/timestamps?query=…` | Find relevant timestamps |
| `GET`  | `/api/documents/{id}/presigned-url` | Get file download URL |

### Chat
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/chat/{doc_id}/stream` | Streaming SSE chat |
| `GET`  | `/api/chat/{doc_id}/sessions` | List chat sessions |
| `GET`  | `/api/chat/sessions/{id}/history` | Get message history |
| `DELETE` | `/api/chat/sessions/{id}` | Delete chat session |

**Authentication:** All endpoints (except `/api/auth/*`) require `Authorization: Bearer <token>`.

---

## 🧪 Testing

```bash
cd backend

# Run all tests with coverage report
pytest -v

# Watch mode (requires pytest-watch)
ptw

# Coverage HTML report
pytest --cov=app --cov-report=html
open htmlcov/index.html
```

Target: **≥95% coverage** across `app/` (enforced in CI).

---

## 🐳 Docker Compose Services

| Service | Image | Purpose |
|---------|-------|---------|
| `db` | `pgvector/pgvector:pg16` | PostgreSQL with vector extension |
| `redis` | `redis:7-alpine` | Caching + rate limiting |
| `minio` | `minio/minio` | S3-compatible file storage |
| `backend` | (built from `backend/Dockerfile`) | FastAPI app |
| `frontend` | (built from `Dockerfile.frontend`) | Next.js app |

---

## ⚙️ Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | — | **Required.** JWT signing key |
| `GROQ_API_KEY` | — | **Required.** Groq API key |
| `DATABASE_URL` | `postgresql+asyncpg://…` | PostgreSQL connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `MINIO_ENDPOINT` | `localhost:9000` | MinIO host:port |
| `WHISPER_MODEL` | `base` | Whisper model size (tiny/base/small) |
| `GROQ_MODEL` | `llama-3.1-70b-versatile` | LLM model name |
| `RATE_LIMIT` | `30/minute` | API rate limit |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend URL for frontend |

See [`.env.example`](.env.example) for the full list.

---

## 🚢 Deployment (Render.com)

1. Push to GitHub
2. Create a **Web Service** from the repo (backend)  
   - Build: `pip install .`  
   - Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Create a **Static Site** or another Web Service for frontend
4. Add managed PostgreSQL + Redis from Render dashboard
5. Set all environment variables in Render settings

---

## 📁 Project Structure

```
doc-chatbot/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI entry point
│   │   ├── core/                 # Config, DB, cache, storage, security
│   │   ├── models/               # SQLAlchemy models
│   │   ├── schemas/              # Pydantic schemas
│   │   ├── api/routes/           # Auth, Documents, Chat routes
│   │   └── services/             # LLM, embeddings, transcription, processor
│   ├── tests/                    # pytest suite (95%+ coverage)
│   ├── Dockerfile
│   └── pyproject.toml
├── app/                          # Next.js App Router
│   ├── (auth)/login & register   # Auth pages
│   └── (dashboard)/              # Protected pages
│       ├── documents/            # List + Chat pages
│       └── upload/               # Upload page
├── components/                   # React components
├── lib/                          # API client + auth helpers
├── docker-compose.yml
├── .github/workflows/ci.yml      # GitHub Actions CI/CD
└── .env.example
```

---

## 📜 License

MIT © 2024
