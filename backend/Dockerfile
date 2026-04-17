# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS builder

WORKDIR /app

# Only install essential build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml .
# We need the app directory to build the package
COPY backend/app ./app

ENV PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1
RUN pip install --upgrade pip \
    && pip install --no-cache-dir --prefix=/install .

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS runtime

# Copy static ffmpeg (Fast and memory-efficient)
COPY --from=mwader/static-ffmpeg:7.0 /ffmpeg /usr/local/bin/
COPY --from=mwader/static-ffmpeg:7.0 /ffprobe /usr/local/bin/

WORKDIR /app

# Runtime system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./alembic.ini

# Create a non-root user
RUN useradd -m -u 1001 appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
