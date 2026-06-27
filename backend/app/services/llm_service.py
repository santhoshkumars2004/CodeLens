"""
CodeLens LLM Service.

Wraps the Groq API to call LLaMA3 for answer generation.
Groq free tier: 6000 requests/day, fast inference.
"""

from typing import Dict, Any

from groq import Groq

from app.config import get_settings
from app.utils.logger import get_logger
from app.utils.metrics import llm_tokens_used, llm_latency_seconds

logger = get_logger(__name__)
settings = get_settings()

# Singleton client
_client: Groq | None = None


def get_groq_client() -> Groq:
    """Get or initialize the Groq client (singleton)."""
    global _client
    if _client is None:
        if not settings.groq_api_key:
            raise ValueError(
                "GROQ_API_KEY is required. Get a free key at console.groq.com"
            )
        _client = Groq(api_key=settings.groq_api_key)
        logger.info("groq_client_initialized", model=settings.groq_model)
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
        context_chunks: Retrieved code chunks with metadata.
        repo_id: Repository identifier for context.

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

        context_parts.append(
            f"[Source {i+1}] File: {file_path} (Lines {start_line}-{end_line})\n"
            f"```\n{content}\n```"
        )

    context_text = "\n\n".join(context_parts)

    system_prompt = (
        "You are CodeLens, an expert code analyst. You answer questions about "
        "codebases based ONLY on the provided source code context.\n\n"
        "ALWAYS respond in EXACTLY this format — no exceptions:\n\n"
        "📝 EXPLANATION\n"
        "[2-3 sentences explaining what the code does in plain English]\n\n"
        "💻 CODE\n"
        "[exact relevant code snippet from the retrieved context]\n\n"
        "📄 SOURCE\n"
        "[file_path:start_line-end_line]\n\n"
        "STRICT RULES:\n"
        "1. NEVER make up code. Only use code from the provided context.\n"
        "2. Explanation must be plain English — no jargon where possible.\n"
        "3. Source must always cite exact file path and line numbers from the context.\n"
        "4. If the context has no relevant answer, say so in the EXPLANATION section.\n"
        f"5. Repository: {repo_id}"
    )

    user_prompt = (
        f"CODE CONTEXT:\n{context_text}\n\n"
        f"QUESTION: {question}\n\n"
        "Provide a clear answer strictly following the required format."
    )

    import time
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

    duration = time.time() - start_time
    llm_latency_seconds.observe(duration)

    # Track token usage
    usage = response.usage
    if usage:
        llm_tokens_used.labels(type="prompt").inc(usage.prompt_tokens)
        llm_tokens_used.labels(type="completion").inc(usage.completion_tokens)

    answer = response.choices[0].message.content

    logger.info(
        "llm_response_generated",
        model=settings.groq_model,
        prompt_tokens=usage.prompt_tokens if usage else 0,
        completion_tokens=usage.completion_tokens if usage else 0,
        duration_seconds=round(duration, 2),
    )

    return {
        "answer": answer,
        "model": settings.groq_model,
        "prompt_tokens": usage.prompt_tokens if usage else 0,
        "completion_tokens": usage.completion_tokens if usage else 0,
        "duration_seconds": duration,
    }
