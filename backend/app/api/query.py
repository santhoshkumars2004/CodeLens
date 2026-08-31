"""
CodeLens Query Endpoint.

POST /api/query — ask a question about an indexed repository.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models.request_models import QueryRequest
from app.models.response_models import QueryResponse
from app.query.pipeline import query_pipeline
from app.query.stream_pipeline import stream_query_pipeline
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


@router.post("/query/stream")
async def query_repo_stream(request: QueryRequest, user_id: str = Depends(get_current_user)):
    """
    Stream an AI answer as Server-Sent Events.

    The client receives:
      1. A "citations" event immediately after retrieval+rerank (< 1s)
      2. Multiple "token" events — one per LLM output token
      3. A "done" event with final metadata

    This makes the perceived latency < 1s vs 10-20s for the blocking endpoint.
    """
    try:
        logger.info(
            "stream_query_request",
            repo_id=request.repo_id,
            question=request.question[:100],
        )

        where_filter = None
        if request.language_filter:
            where_filter = {"language": {"$eq": request.language_filter.lower()}}

        async def event_generator():
            async for event in stream_query_pipeline(
                question=request.question,
                repo_id=request.repo_id,
                top_k=request.top_k or 5,
                where=where_filter,
                path_filter=request.path_filter,
                user_id=user_id,
            ):
                yield event

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control":    "no-cache",
                "X-Accel-Buffering": "no",   # Disable nginx buffering
                "Connection":       "keep-alive",
            },
        )

    except Exception as e:
        logger.error("stream_query_error", repo_id=request.repo_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Stream failed: {e}")
