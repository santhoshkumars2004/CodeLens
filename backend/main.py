"""
CodeLens — AI-Powered Codebase Q&A System.

FastAPI application entry point. Configures CORS, routing,
middleware, Prometheus metrics, and structured logging.
"""

import os

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import get_settings
from app.utils.logger import setup_logging, get_logger
from app.api import health, ingest, query, repos

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    setup_logging(settings.log_level)
    logger = get_logger("main")
    logger.info(
        "codelens_starting",
        version=settings.app_version,
        debug=settings.debug,
    )
    yield
    logger.info("codelens_shutting_down")


# ── Create FastAPI Application ──────────────────────────────────────
app = FastAPI(
    title="CodeLens API",
    description=(
        "AI-powered codebase Q&A system. Index GitHub repositories "
        "and ask natural language questions with cited answers."
    ),
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS Middleware ─────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
        "http://localhost:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Prometheus Metrics ──────────────────────────────────────────────
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# ── Register API Routes ────────────────────────────────────────────
app.include_router(health.router)
app.include_router(ingest.router)
app.include_router(query.router)
app.include_router(repos.router)


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=settings.debug,
    )
