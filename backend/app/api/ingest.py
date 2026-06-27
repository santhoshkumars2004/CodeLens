"""
StackSense Ingest Endpoint.

POST /api/ingest               — start indexing a GitHub repository (returns 202).
GET  /api/ingest/status/{owner}/{repo} — poll ingestion progress.
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from fastapi.responses import JSONResponse

from app.models.request_models import IngestRequest
from app.ingestion.pipeline import ingest_repository_background, get_ingestion_status
from app.ingestion.cloner import parse_repo_url
from app.utils.logger import get_logger

router = APIRouter(prefix="/api", tags=["Ingestion"])
logger = get_logger(__name__)


@router.post("/ingest", status_code=status.HTTP_202_ACCEPTED)
async def ingest_repo(
    request: IngestRequest,
    background_tasks: BackgroundTasks,
):
    """
    Start indexing a GitHub repository.

    Returns **202 Accepted** immediately and runs the full
    clone → filter → chunk → embed → store pipeline in the background.

    Poll `GET /api/ingest/status/{owner}/{repo}` to track progress.
    """
    try:
        repo_info = parse_repo_url(request.repo_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    repo_id = repo_info["repo_id"]
    owner   = repo_info["owner"]
    repo    = repo_info["repo"]

    logger.info("ingest_accepted", repo_id=repo_id)

    # Kick off ingestion in the background — connection closes immediately
    background_tasks.add_task(
        ingest_repository_background,
        repo_url=request.repo_url,
        branch=request.branch,
    )

    return JSONResponse(
        status_code=202,
        content={
            "repo_id": repo_id,
            "status":  "accepted",
            "message": f"Ingestion started for {repo_id}. Poll the status endpoint for progress.",
            "status_url": f"/api/ingest/status/{owner}/{repo}",
        },
    )


@router.get("/ingest/status/{owner}/{repo}", tags=["Ingestion"])
async def check_ingestion_status(owner: str, repo: str):
    """
    Check live progress of a repository ingestion.

    Returns the current status, progress percentage, and a human-readable
    message. Possible status values: cloning | discovering | chunking |
    embedding | storing | completed | error.
    """
    repo_id = f"{owner}/{repo}"
    ingestion_status = get_ingestion_status(repo_id)

    if ingestion_status is None:
        raise HTTPException(
            status_code=404,
            detail=f"No ingestion found for {repo_id}. Submit POST /api/ingest first.",
        )

    return {"repo_id": repo_id, **ingestion_status}
