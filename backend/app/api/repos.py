"""
CodeLens Repos Endpoint.

GET /api/repos              — list all indexed repositories.
GET /api/repos/{owner}/{repo}/files — list all files in a repo (file explorer).
DELETE /api/repos/{owner}/{repo}    — delete an indexed repository.
"""

from fastapi import APIRouter

from app.models.response_models import RepoListResponse, RepoInfo
from app.vectordb.vector_store import list_collections, delete_collection, get_repo_files
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


@router.get("/repos/{owner}/{repo}/files")
async def get_repo_file_tree(owner: str, repo: str):
    """
    List all indexed files for a repository, organized for file explorer UI.

    Returns file paths with language and chunk count so the frontend
    can build a collapsible directory tree.
    """
    repo_id = f"{owner}/{repo}"
    try:
        result = get_repo_files(repo_id)
        return result
    except Exception as e:
        logger.error("get_repo_files_error", repo_id=repo_id, error=str(e))
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Failed to list files: {e}")


@router.delete("/repos/{owner}/{repo}")
async def delete_repo(owner: str, repo: str):
    """Delete an indexed repository from ChromaDB."""
    repo_id = f"{owner}/{repo}"
    success = delete_collection(repo_id)
    if not success:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Failed to delete repository collection")
    return {"status": "success", "message": f"Deleted repository {repo_id}"}

