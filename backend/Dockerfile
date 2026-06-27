# StackSense Backend Dockerfile
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

# COPY requirements first — Docker caches this layer.
# As long as requirements.txt doesn't change, pip install is SKIPPED on
# subsequent builds (huge speed improvement in CI/CD pipelines).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Stage 2: Application ───────────────────────────────────────────
COPY . .

# Pre-create data directories so they exist even if volume isn't mounted
RUN mkdir -p /app/data/chromadb /tmp/stacksense_repos

# Expose the port (documentation only — actual binding is in CMD)
EXPOSE 8000

# Health check — Docker will mark the container "unhealthy" if this fails
# Used by docker-compose depends_on and Kubernetes liveness probes
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# IMPORTANT: --host 0.0.0.0 means accept connections from outside the container.
# Using 127.0.0.1 here would make the service unreachable from the host machine.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
