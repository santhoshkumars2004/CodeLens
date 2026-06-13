"""
StackSense Repos Endpoint.

GET /api/repos — list all indexed repositories.
"""

from fastapi import APIRouter

from app.models.response_models import RepoListResponse, RepoInfo
from app.services.chromadb_service import list_collections
from app.utils.logger import get_logger

router = APIRouter(prefix="/api", tags=["Repositories"])
logger = get_logger(__name__)


@router.get("/repos", response_model=RepoListResponse)
async def list_repos():
    """List all indexed repositories with their stats."""
    collections = list_collections()

    repos = []
    for col in collections:
        repos.append(RepoInfo(
            repo_id=col["repo_id"],
            repo_url=f"https://github.com/{col['repo_id']}",
            files_indexed=0,  # Would need metadata store for this
            chunks_count=col["count"],
            languages=[],
            indexed_at="",
            status="indexed",
        ))

    return RepoListResponse(repos=repos, total=len(repos))
