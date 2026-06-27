"""
CodeLens Health Check Endpoint.

GET /health — returns system health status.
"""

from datetime import datetime

from fastapi import APIRouter

from app.config import get_settings
from app.models.response_models import HealthResponse
from app.vectordb.vector_store import is_connected

router = APIRouter()
settings = get_settings()


@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Check if the backend and its dependencies are healthy."""
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        chromadb_connected=is_connected(),
        timestamp=datetime.utcnow().isoformat(),
    )
