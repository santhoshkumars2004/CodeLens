"""
CodeLens — LLM Client (app/llm/client.py)

Wraps the Groq API to call LLaMA3 for answer generation.
Groq free tier: 6000 requests/day, fast inference.

Replaces: app/services/llm_service.py
"""

import time
from typing import Dict, Any, Generator

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

    # Build context from chunks — truncate each to avoid 6000 TPM limit on Groq free tier
    MAX_CHARS_PER_CHUNK = 1500  # 1500 chars ≈ ~375 tokens per chunk, 5 chunks ≈ ~2000 tokens
    context_parts = []
    for i, chunk in enumerate(context_chunks):
        meta = chunk.get("metadata", {})
        file_path = meta.get("file_path", "unknown")
        start_line = meta.get("start_line", "?")
        end_line = meta.get("end_line", "?")
        content = chunk.get("content", "")
        # Truncate long chunks to keep total prompt under 5000 tokens
        if len(content) > MAX_CHARS_PER_CHUNK:
            content = content[:MAX_CHARS_PER_CHUNK] + "... [truncated]"
        score = chunk.get("rerank_score", chunk.get("relevance_score", 0))

        context_parts.append(
            f"[Source {i+1}] File: {file_path} (Lines {start_line}-{end_line}) "
            f"| Relevance: {round(score, 3)}\n"
            f"```\n{content}\n```"
        )

    context_text = "\n\n".join(context_parts)

    system_prompt = (
        "You are CodeLens, an expert senior software engineer and code analyst. "
        "You answer developer questions about a codebase based ONLY on the provided source code context.\n\n"
        "ALWAYS respond in EXACTLY this format — no exceptions:\n\n"
        "## 📝 Explanation\n"
        "[Write a thorough, developer-friendly explanation. Cover:\n"
        " - What this code does at a high level (1-2 sentences)\n"
        " - HOW it works step by step (walk through key logic, conditions, loops)\n"
        " - WHY it is designed this way (intent, trade-offs, patterns used)\n"
        " - Any important edge cases, error handling, or things to watch out for\n"
        "Minimum 4-6 sentences. Be thorough — a junior developer should fully understand after reading this.]\n\n"
        "## 💻 Code\n"
        "```language\n"
        "[The most relevant code snippet from the context — paste it clean, no metadata headers]\n"
        "```\n\n"
        "## 📄 Source\n"
        "`[file_path]` Lines [start_line]-[end_line]\n\n"
        "STRICT RULES:\n"
        "1. NEVER make up code. Only use code from the provided context.\n"
        "2. ALWAYS quote exact variable names, function names, and constants "
        "as they appear in the code (e.g. say `rerank_score`, not 'the ranking score'; "
        "say `MAX_FILE_SIZE_BYTES`, not 'the size limit'). This is critical.\n"
        "3. Explanation must be plain English — no jargon where possible. Write as if explaining to a junior developer.\n"
        "4. Source must always cite exact file path and line numbers from the context.\n"
        "5. If the context has no relevant answer, say so in the Explanation section and explain what you DID find.\n"
        "6. Always use proper markdown headings (##) for each section.\n"
        "7. In the Code section, paste ONLY the raw code — never include metadata lines like 'File:', 'Language:', 'Function:', 'Source:'.\n"
        f"8. Repository: {repo_id}"
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
        max_tokens=2048,  # increased for richer explanations
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


def _build_prompts(
    question: str,
    context_chunks: list[Dict[str, Any]],
    repo_id: str,
) -> tuple[str, str]:
    """Shared prompt-building logic used by both streaming and non-streaming paths."""
    MAX_CHARS_PER_CHUNK = 1500
    context_parts = []
    for i, chunk in enumerate(context_chunks):
        meta = chunk.get("metadata", {})
        file_path = meta.get("file_path", "unknown")
        start_line = meta.get("start_line", "?")
        end_line = meta.get("end_line", "?")
        content = chunk.get("content", "")
        if len(content) > MAX_CHARS_PER_CHUNK:
            content = content[:MAX_CHARS_PER_CHUNK] + "... [truncated]"
        score = chunk.get("rerank_score", chunk.get("relevance_score", 0))
        context_parts.append(
            f"[Source {i+1}] File: {file_path} (Lines {start_line}-{end_line}) "
            f"| Relevance: {round(score, 3)}\n"
            f"```\n{content}\n```"
        )

    context_text = "\n\n".join(context_parts)

    system_prompt = (
        "You are CodeLens, an expert senior software engineer and code analyst. "
        "You answer developer questions about a codebase based ONLY on the provided source code context.\n\n"
        "ALWAYS respond in EXACTLY this format — no exceptions:\n\n"
        "## 📝 Explanation\n"
        "[Write a thorough, developer-friendly explanation. Cover:\n"
        " - What this code does at a high level (1-2 sentences)\n"
        " - HOW it works step by step (walk through key logic, conditions, loops)\n"
        " - WHY it is designed this way (intent, trade-offs, patterns used)\n"
        " - Any important edge cases, error handling, or things to watch out for\n"
        "Minimum 4-6 sentences. Be thorough — a junior developer should fully understand after reading this.]\n\n"
        "## 💻 Code\n"
        "```language\n"
        "[The most relevant code snippet from the context — paste it clean, no metadata headers]\n"
        "```\n\n"
        "## 📄 Source\n"
        "`[file_path]` Lines [start_line]-[end_line]\n\n"
        "STRICT RULES:\n"
        "1. NEVER make up code. Only use code from the provided context.\n"
        "2. ALWAYS quote exact variable names, function names, and constants "
        "as they appear in the code.\n"
        "3. Explanation must be plain English — no jargon where possible. Write as if explaining to a junior developer.\n"
        "4. Source must always cite exact file path and line numbers from the context.\n"
        "5. If the context has no relevant answer, say so in the Explanation section and explain what you DID find.\n"
        "6. Always use proper markdown headings (##) for each section.\n"
        "7. In the Code section, paste ONLY the raw code — never include metadata lines like 'File:', 'Language:', 'Function:', 'Source:'.\n"
        f"8. Repository: {repo_id}"
    )

    user_prompt = (
        f"CODE CONTEXT:\n{context_text}\n\n"
        f"QUESTION: {question}\n\n"
        "Provide a clear answer strictly following the required format."
    )

    return system_prompt, user_prompt


def generate_answer_stream(
    question: str,
    context_chunks: list[Dict[str, Any]],
    repo_id: str,
) -> Generator[str, None, None]:
    """
    Stream token deltas from Groq LLaMA3 using the same RAG context as generate_answer().

    Yields each text delta string as it arrives from the API.
    The caller is responsible for assembling the full answer.
    """
    client = get_groq_client()
    system_prompt, user_prompt = _build_prompts(question, context_chunks, repo_id)

    logger.info(
        "llm_stream_start",
        model=settings.groq_model,
        context_chunks=len(context_chunks),
    )

    stream = client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=settings.groq_temperature,
        max_tokens=2048,  # increased for richer explanations
        stream=True,
    )

    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta

