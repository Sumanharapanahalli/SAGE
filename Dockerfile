# ==============================================================================
# Sage Framework — Dockerfile (Backend)
# ==============================================================================
# Runs on CPU-only machines (no GPU required for Gemini CLI mode).
# For production deployments use deploy/docker/Dockerfile.backend instead —
# it has tighter uvicorn flags and resource annotations.
# ==============================================================================

FROM python:3.11-slim

# System deps: curl for HEALTHCHECK, git + build-essential for C extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps — copy requirements.txt first to exploit Docker layer cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY src/        ./src/
COPY config/     ./config/
COPY solutions/  ./solutions/

# Create runtime data directories (audit DB, vector store, model cache).
# In production these are bind-mounted via SAGE_SOLUTIONS_DIR / sage-data volume.
RUN mkdir -p data/chroma_db data/models

# Environment defaults — all overridable at container runtime
ENV SAGE_PROJECT=starter \
    LLM_PROVIDER=gemini \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUTF8=1 \
    PYTHONIOENCODING=utf-8

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Single uvicorn worker — LLMGateway uses threading.Lock; scale by running
# multiple containers rather than multiple workers in one container.
CMD ["python", "-m", "uvicorn", "src.interface.api:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--timeout-keep-alive", "30"]
