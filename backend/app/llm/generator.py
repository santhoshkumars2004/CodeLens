"""
StackSense — Generator (app/llm/generator.py)

Builds the prompt, calls the LLM client, and formats the response
with source citations from chunk metadata.

Replaces: app/core/generator.py
"""

from typing import Dict, Any, List

from app.llm.client import generate_answer
from app.utils.logger import get_logger

logger = get_logger(__name__)


def generate(
    question: str,
    chunks: List[Dict[str, Any]],
    repo_id: str,
) -> Dict[str, Any]:
    """
    Generate an answer from retrieved chunks using the LLM.

    Args:
        question: User's question.
        chunks: Relevant, reranked code chunks with metadata.
        repo_id: Repository identifier.

    Returns:
        Dict with answer, citations, and token usage.
    """
    logger.info(
        "llm_build_context",
        chunks=len(chunks),
        repo_id=repo_id,
    )

    result = generate_answer(question, chunks, repo_id)

    # Build citations list from chunk metadata
    citations = []
    for chunk in chunks:
        meta = chunk.get("metadata", {})
        citations.append({
            "file_path": meta.get("file_path", "unknown"),
            "start_line": meta.get("start_line", 0),
            "end_line": meta.get("end_line", 0),
            "content": chunk.get("content", ""),
            "language": meta.get("language", "unknown"),
            "relevance_score": round(
                chunk.get("rerank_score", chunk.get("relevance_score", 0)), 4
            ),
        })

    logger.info(
        "llm_answer_ready",
        citations=len(citations),
        answer_length=len(result["answer"]),
    )

    return {
        "answer": result["answer"],
        "citations": citations,
        "model": result["model"],
        "prompt_tokens": result["prompt_tokens"],
        "completion_tokens": result["completion_tokens"],
    }
