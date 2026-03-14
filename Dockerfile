# ==============================================================================
# Sage Framework — Dockerfile (Backend)
# ==============================================================================
# Multi-stage build for minimal image size.
# Runs on CPU-only machines (no GPU required for Gemini CLI mode).
# ==============================================================================

FROM python:3.11-slim AS base

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps — install in layers for better cache
COPY requirements.txt .

# Install core deps (always)
RUN pip install --no-cache-dir \
    pyyaml pydantic fastapi uvicorn \
    python-dotenv requests httpx \
    chromadb langchain langchain-community langchain-chroma \
    langchain-huggingface sentence-transformers \
    pandas numpy fastmcp

# Install optional deps (skip on failure for minimal environments)
RUN pip install --no-cache-dir python-pptx || true

# Copy application
COPY src/        ./src/
COPY config/     ./config/
COPY solutions/  ./solutions/

# Create data directories
RUN mkdir -p data/chroma_db data/models

# Environment defaults
ENV SAGE_PROJECT=starter \
    LLM_PROVIDER=gemini \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "src/main.py", "api", "--host", "0.0.0.0", "--port", "8000"]
