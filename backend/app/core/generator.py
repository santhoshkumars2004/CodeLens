"""
CodeLens Generator.

Wraps the LLM service with prompt building and response parsing
for code Q&A generation.
"""

from typing import Dict, Any, List

from app.services.llm_service import generate_answer
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
        chunks: Relevant code chunks with metadata.
        repo_id: Repository identifier.

    Returns:
        Dict with answer, citations, and metadata.
    """
    result = generate_answer(question, chunks, repo_id)

    # Build citations from chunks
    citations = []
    for chunk in chunks:
        meta = chunk.get("metadata", {})
        citations.append({
            "file_path": meta.get("file_path", "unknown"),
            "start_line": meta.get("start_line", 0),
            "end_line": meta.get("end_line", 0),
            "content": chunk.get("content", "")[:500],  # Truncate
            "language": meta.get("language", "unknown"),
            "relevance_score": round(
                chunk.get("rerank_score", chunk.get("relevance_score", 0)), 4
            ),
        })

    return {
        "answer": result["answer"],
        "citations": citations,
        "model": result["model"],
        "prompt_tokens": result["prompt_tokens"],
        "completion_tokens": result["completion_tokens"],
    }
