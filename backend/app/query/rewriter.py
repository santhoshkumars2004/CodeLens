"""
StackSense — Query Rewriter (app/query/rewriter.py)

Rewrites a user's natural language question into a code-search-optimized
query before embedding. This bridges the vocabulary gap between how humans
ask questions ("how does login work?") and how code is written
("authenticate_user JWT token verify password hash").

Uses the same Groq LLaMA-3 API that is already configured — no extra cost.
"""

from groq import Groq
from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=settings.groq_api_key)
    return _client


def rewrite_query(question: str) -> str:
    """
    Rewrite a natural language question into a code-search-optimized query.

    The rewritten query expands abbreviations, adds likely function/variable
    names, and strips conversational filler — making it much better for
    dense embedding and BM25 keyword search alike.

    Args:
        question: The raw question from the user.

    Returns:
        A rewritten, code-search-friendly version of the question.
        Falls back to the original question on any error.
    """
    if not settings.groq_api_key:
        # No API key configured — skip rewriting silently
        return question

    try:
        client = _get_client()

        system_prompt = (
            "You are a code search query optimizer. "
            "Your ONLY job is to rewrite the user's question into a short, "
            "keyword-rich search query optimized for searching source code. "
            "Rules:\n"
            "1. Expand natural language into likely function names, class names, variable names, and code concepts.\n"
            "2. Remove conversational filler words ('how does', 'can you', 'what is', etc.).\n"
            "3. Include synonyms for technical terms (e.g., 'login' → 'authenticate login user session token').\n"
            "4. Output ONLY the rewritten query — no explanation, no preamble, no quotes.\n"
            "5. Keep it under 30 words.\n"
            "Examples:\n"
            "  Input:  'how does login work?'\n"
            "  Output: authenticate login user session JWT token password hash verify\n\n"
            "  Input:  'where are database connections set up?'\n"
            "  Output: database connection pool setup initialize config connect SQLAlchemy engine\n\n"
            "  Input:  'explain the file upload feature'\n"
            "  Output: file upload handler multipart form data save storage validate size type"
        )

        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            temperature=0.0,   # deterministic — always same rewrite for same input
            max_tokens=60,     # short output only
        )

        rewritten = response.choices[0].message.content.strip()

        logger.info(
            "query_rewritten",
            original=question[:80],
            rewritten=rewritten[:120],
        )

        return rewritten

    except Exception as e:
        # Never crash on rewrite failure — just use original question
        logger.warning("query_rewrite_failed", error=str(e), fallback="original")
        return question
