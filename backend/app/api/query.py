"""
CodeLens Query Endpoint.

POST /api/query — ask a question about an indexed repository.
"""

from fastapi import APIRouter, HTTPException

from app.models.request_models import QueryRequest
from app.models.response_models import QueryResponse
from app.query.pipeline import query_pipeline
from app.utils.logger import get_logger
from app.api.auth import get_current_user
from fastapi import Depends, APIRouter, HTTPException
from app.db.supabase import save_chat_history, get_chat_history
from app.utils.logger import get_logger

router = APIRouter(prefix="/api", tags=["Query"])
logger = get_logger(__name__)


@router.post("/query", response_model=QueryResponse)
async def query_repo(request: QueryRequest, user_id: str = Depends(get_current_user)):
    """
    Ask a natural language question about an indexed codebase.

    Returns an AI-generated answer with exact file:line citations.
    """
    try:
        logger.info(
            "query_request",
            repo_id=request.repo_id,
            question=request.question[:100],
        )

        # Build metadata filter for ChromaDB (where clause)
        where_filter = None
        if request.language_filter:
            where_filter = {"language": {"$eq": request.language_filter.lower()}}

        result = await query_pipeline(
            question=request.question,
            repo_id=request.repo_id,
            top_k=request.top_k or 5,
            where=where_filter,
            path_filter=request.path_filter,
        )

        # Save to Supabase (Option B)
        save_chat_history(
            user_id=user_id,
            repo_id=request.repo_id,
            question=request.question,
            answer=result["answer"],
            citations=result["citations"]
        )

        return QueryResponse(**result)

    except Exception as e:
        logger.error(
            "query_error",
            repo_id=request.repo_id,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")

@router.get("/query/history/{owner}/{repo}")
async def fetch_history(owner: str, repo: str, user_id: str = Depends(get_current_user)):
    """
    Fetch the user's previous chat history for a specific repository.
    """
    repo_id = f"{owner}/{repo}"
    try:
        history = get_chat_history(user_id=user_id, repo_id=repo_id)
        
        # Transform Supabase DB records into Message objects the frontend expects
        messages = []
        for row in history:
            # User question
            messages.append({
                "id": f"{row['id']}-q",
                "role": "user",
                "content": row["question"],
                "timestamp": row["created_at"]
            })
            # AI answer
            messages.append({
                "id": f"{row['id']}-a",
                "role": "assistant",
                "content": row["answer"],
                "citations": row.get("citations"),
                "timestamp": row["created_at"]
            })
            
        return {"messages": messages}
    except Exception as e:
        logger.error("fetch_history_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch history")
