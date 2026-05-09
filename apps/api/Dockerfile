# Production image for the FastAPI app.
# Multi-stage so the runtime layer is tiny.

FROM python:3.11-slim AS builder

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.8.17 /uv /usr/local/bin/uv

WORKDIR /app

# Copy workspace metadata + sources we need to build the api package.
COPY pyproject.toml uv.lock ./
COPY packages/shared ./packages/shared
COPY apps/api ./apps/api
COPY mcp ./mcp

RUN uv sync --all-packages --frozen --no-dev

# ---- Runtime ----------------------------------------------------------

FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* && \
    useradd --create-home --uid 1001 app

WORKDIR /app

COPY --from=builder /app /app
COPY seeds ./seeds
COPY infra/alembic ./infra/alembic

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8000/healthz || exit 1

CMD ["uvicorn", "api.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
