"""
CodeLens Repos Endpoint.

GET /api/repos              — list all indexed repositories.
GET /api/repos/{owner}/{repo}/files       — file explorer.
GET /api/repos/{owner}/{repo}/suggestions — AI-generated starter questions.
DELETE /api/repos/{owner}/{repo}          — delete an indexed repository.
"""

from fastapi import APIRouter, HTTPException

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
            files_indexed=0,
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
    """
    repo_id = f"{owner}/{repo}"
    try:
        result = get_repo_files(repo_id)
        return result
    except Exception as e:
        logger.error("get_repo_files_error", repo_id=repo_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list files: {e}")


@router.get("/repos/{owner}/{repo}/suggestions")
async def get_repo_suggestions(owner: str, repo: str):
    """
    Generate 5 AI-powered starter questions for this repository.

    Uses the file list from ChromaDB to understand the codebase structure,
    then asks the LLM to generate specific, useful questions a developer
    would actually want to ask.

    Returns fast by skipping rerank/retrieval — just file structure + LLM.
    """
    repo_id = f"{owner}/{repo}"
    try:
        # Get file tree to understand repo structure
        file_data = get_repo_files(repo_id)
        files = file_data.get("files", [])
        languages = file_data.get("languages", [])

        if not files:
            return {"suggestions": _default_suggestions()}

        # Build a compact file list for the prompt (max 40 files)
        file_lines = []
        for f in files[:40]:
            file_lines.append(f"  {f['file_path']} ({f['language']}, {f['chunk_count']} chunks)")
        file_summary = "\n".join(file_lines)
        lang_str = ", ".join(languages) if languages else "unknown"

        prompt = (
            f"You are analyzing a GitHub repository called '{repo_id}'.\n\n"
            f"Languages: {lang_str}\n"
            f"File structure ({len(files)} files):\n{file_summary}\n\n"
            "Generate EXACTLY 5 specific, useful questions a developer would ask about this codebase.\n"
            "Rules:\n"
            "- Each question must be answerable by looking at the code\n"
            "- Reference specific file names or concepts you see in the structure\n"
            "- Make them concrete (e.g. 'How does auth.py handle JWT tokens?') not generic\n"
            "- One question per line, no numbering, no bullets\n"
            "- Keep each question under 12 words\n\n"
            "5 questions:"
        )

        from app.llm.client import get_groq_client
        from app.config import get_settings
        settings = get_settings()
        client = get_groq_client()

        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.7,
        )

        raw = response.choices[0].message.content.strip()
        # Parse into list — one question per line, skip blank lines
        questions = [
            q.strip().lstrip("0123456789.-) ")
            for q in raw.split("\n")
            if q.strip() and len(q.strip()) > 10
        ][:5]

        # Pad with defaults if LLM gave fewer than 3
        if len(questions) < 3:
            questions = _default_suggestions()

        logger.info("suggestions_generated", repo_id=repo_id, count=len(questions))
        return {"suggestions": questions, "repo_id": repo_id}

    except Exception as e:
        logger.warning("suggestions_failed", repo_id=repo_id, error=str(e))
        return {"suggestions": _default_suggestions()}


def _default_suggestions() -> list[str]:
    """Fallback questions if LLM call fails."""
    return [
        "How does authentication work?",
        "Where is the main entry point?",
        "Explain the database schema",
        "How are API routes structured?",
        "What error handling patterns are used?",
    ]


@router.delete("/repos/{owner}/{repo}")
async def delete_repo(owner: str, repo: str):
    """Delete an indexed repository from ChromaDB."""
    repo_id = f"{owner}/{repo}"
    success = delete_collection(repo_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete repository collection")
    return {"status": "success", "message": f"Deleted repository {repo_id}"}
