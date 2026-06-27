"""
CodeLens Repos Endpoint.

GET /api/repos — list all indexed repositories.
"""

from fastapi import APIRouter

from app.models.response_models import RepoListResponse, RepoInfo
from app.vectordb.vector_store import list_collections, delete_collection
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


@router.delete("/repos/{owner}/{repo}")
async def delete_repo(owner: str, repo: str):
    """Delete an indexed repository from ChromaDB."""
    repo_id = f"{owner}/{repo}"
    success = delete_collection(repo_id)
    if not success:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Failed to delete repository collection")
    return {"status": "success", "message": f"Deleted repository {repo_id}"}
