"""
StackSense — LLM Client (app/llm/client.py)

Wraps the Groq API to call LLaMA3 for answer generation.
Groq free tier: 6000 requests/day, fast inference.

Replaces: app/services/llm_service.py
"""

import time
from typing import Dict, Any

from groq import Groq

from app.config import get_settings
from app.utils.logger import get_logger
from app.utils.metrics import llm_tokens_used, llm_latency_seconds

logger = get_logger(__name__)
settings = get_settings()

# Singleton Groq client
_client: Groq | None = None


def get_groq_client() -> Groq:
    """Get or initialize the Groq API client (singleton)."""
    global _client
    if _client is None:
        if not settings.groq_api_key:
            raise ValueError(
                "GROQ_API_KEY is required. Get a free key at console.groq.com"
            )
        _client = Groq(api_key=settings.groq_api_key)
        logger.info("llm_client_ready", model=settings.groq_model)
    return _client


def generate_answer(
    question: str,
    context_chunks: list[Dict[str, Any]],
    repo_id: str,
) -> Dict[str, Any]:
    """
    Generate an answer using Groq LLaMA3 with RAG context.

    Args:
        question: User's natural language question.
        context_chunks: Retrieved and reranked code chunks.
        repo_id: Repository identifier for system prompt context.

    Returns:
        Dict with answer text and token usage stats.
    """
    client = get_groq_client()

    # Build context from chunks
    context_parts = []
    for i, chunk in enumerate(context_chunks):
        meta = chunk.get("metadata", {})
        file_path = meta.get("file_path", "unknown")
        start_line = meta.get("start_line", "?")
        end_line = meta.get("end_line", "?")
        content = chunk.get("content", "")
        score = chunk.get("rerank_score", chunk.get("relevance_score", 0))

        context_parts.append(
            f"[Source {i+1}] File: {file_path} (Lines {start_line}-{end_line}) "
            f"| Relevance: {round(score, 3)}\n"
            f"```\n{content}\n```"
        )

    context_text = "\n\n".join(context_parts)

    system_prompt = (
        "You are StackSense, an expert code analyst. You answer questions about "
        "codebases based ONLY on the provided source code context.\n\n"
        "ALWAYS respond in EXACTLY this format — no exceptions:\n\n"
        "## 📝 Explanation\n"
        "[2-3 sentences explaining what the code does in plain English]\n\n"
        "## 💻 Code\n"
        "```language\n"
        "[exact relevant code snippet from the retrieved context]\n"
        "```\n\n"
        "## 📄 Source\n"
        "`[file_path]` Lines [start_line]-[end_line]\n\n"
        "STRICT RULES:\n"
        "1. NEVER make up code. Only use code from the provided context.\n"
        "2. Explanation must be plain English — no jargon where possible.\n"
        "3. Source must always cite exact file path and line numbers from the context.\n"
        "4. If the context has no relevant answer, say so in the Explanation section.\n"
        "5. Always use proper markdown headings (##) for each section.\n"
        f"6. Repository: {repo_id}"
    )

    user_prompt = (
        f"CODE CONTEXT:\n{context_text}\n\n"
        f"QUESTION: {question}\n\n"
        "Provide a clear answer strictly following the required format."
    )

    # Approximate token count for logging
    approx_prompt_tokens = len((system_prompt + user_prompt).split())

    logger.info(
        "llm_generate_start",
        model=settings.groq_model,
        context_chunks=len(context_chunks),
        approx_prompt_tokens=approx_prompt_tokens,
    )

    start_time = time.time()

    response = client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=settings.groq_temperature,
        max_tokens=settings.groq_max_tokens,
    )

    duration = round(time.time() - start_time, 2)
    llm_latency_seconds.observe(duration)

    usage = response.usage
    if usage:
        llm_tokens_used.labels(type="prompt").inc(usage.prompt_tokens)
        llm_tokens_used.labels(type="completion").inc(usage.completion_tokens)

    answer = response.choices[0].message.content

    logger.info(
        "llm_generate_complete",
        model=settings.groq_model,
        prompt_tokens=usage.prompt_tokens if usage else 0,
        completion_tokens=usage.completion_tokens if usage else 0,
        duration_seconds=duration,
    )

    return {
        "answer": answer,
        "model": settings.groq_model,
        "prompt_tokens": usage.prompt_tokens if usage else 0,
        "completion_tokens": usage.completion_tokens if usage else 0,
        "duration_seconds": duration,
    }
