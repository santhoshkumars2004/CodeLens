"""
StackSense Ingest Endpoint.

POST /api/ingest — clone and index a GitHub repository.
GET /api/ingest/status/{repo_id} — check ingestion progress.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks

from app.models.request_models import IngestRequest
from app.models.response_models import IngestResponse
from app.core.ingestion import ingest_repository, get_ingestion_status
from app.services.github_service import parse_repo_url
from app.utils.logger import get_logger

router = APIRouter(prefix="/api", tags=["Ingestion"])
logger = get_logger(__name__)


@router.post("/ingest", response_model=IngestResponse)
async def ingest_repo(
    request: IngestRequest,
    background_tasks: BackgroundTasks,
):
    """
    Ingest a GitHub repository: clone, parse, chunk, embed, and store.

    This is a synchronous operation for now. For large repos, consider
    using the background task approach.
    """
    try:
        # Validate the URL first
        repo_info = parse_repo_url(request.repo_url)
        logger.info("ingest_request", repo_id=repo_info["repo_id"])

        # Run ingestion
        result = ingest_repository(
            repo_url=request.repo_url,
            branch=request.branch,
        )

        return IngestResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error("ingest_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")


@router.get("/ingest/status/{owner}/{repo}", tags=["Ingestion"])
async def check_ingestion_status(owner: str, repo: str):
    """Check the current ingestion status of a repository."""
    repo_id = f"{owner}/{repo}"
    status = get_ingestion_status(repo_id)

    if status is None:
        raise HTTPException(
            status_code=404,
            detail=f"No ingestion found for {repo_id}",
        )

    return {"repo_id": repo_id, **status}
