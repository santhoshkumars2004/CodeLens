# CodeLens Backend Dockerfile
# Multi-stage build for optimized, production-ready image

# ── Stage 1: Dependency installer ──────────────────────────────────
FROM python:3.11-slim AS base

# Install system dependencies
# curl is needed for healthchecks; git for cloning GitHub repos
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# COPY production requirements — excludes sentence-transformers/PyTorch
# to keep the image small enough for Railway's free 500MB RAM limit.
# Local development uses requirements.txt (with PyTorch + Jina AI model).
COPY requirements.prod.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.prod.txt

# ── Stage 2: Application ───────────────────────────────────────────
COPY . .

# Pre-create data directories so they exist even if volume isn't mounted
RUN mkdir -p /app/data/chromadb /tmp/codelens_repos

# Expose the port (documentation only — actual binding is in CMD)
EXPOSE 8000

# Health check — Docker will mark the container "unhealthy" if this fails
# Used by docker-compose depends_on and Kubernetes liveness probes
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# IMPORTANT: --host 0.0.0.0 means accept connections from outside the container.
# Using 127.0.0.1 here would make the service unreachable from the host machine.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
