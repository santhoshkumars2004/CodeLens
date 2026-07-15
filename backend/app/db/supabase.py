"""
Supabase Client Initialization and Helpers
"""
import uuid
from typing import Dict, Any, Optional

from supabase import create_client, Client
from app.config import get_settings
from app.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)

def get_supabase_client() -> Optional[Client]:
    """Returns a Supabase client if configured, otherwise None."""
    if settings.supabase_url and settings.supabase_key:
        return create_client(settings.supabase_url, settings.supabase_key)
    return None

def save_chat_history(user_id: str, repo_id: str, question: str, answer: str, citations: list):
    """Saves a single Q&A interaction to the chat_history table."""
    client = get_supabase_client()
    if not client:
        logger.warning("supabase_not_configured", action="save_chat_history")
        return
        
    try:
        # First ensure user exists in our users table
        # Since we use Clerk, we just upsert the user ID
        client.table("users").upsert({"id": user_id, "email": "user@codelens"}).execute()
        
        # Insert chat record
        data = {
            "user_id": user_id,
            "repo_id": repo_id,
            "question": question,
            "answer": answer,
            "citations": citations
        }
        client.table("chat_history").insert(data).execute()
        logger.info("chat_history_saved", user_id=user_id, repo_id=repo_id)
    except Exception as e:
        logger.error("supabase_error", error=str(e), action="save_chat_history")

def save_user_repo(user_id: str, repo_id: str):
    """Links a user to a repository they ingested."""
    client = get_supabase_client()
    if not client:
        return
        
    try:
        # Upsert user just in case
        client.table("users").upsert({"id": user_id, "email": "user@codelens"}).execute()
        
        # Insert user_repo record (ignoring if it already exists due to UNIQUE constraint)
        client.table("user_repos").upsert({"user_id": user_id, "repo_id": repo_id}, on_conflict="user_id,repo_id").execute()
        logger.info("user_repo_saved", user_id=user_id, repo_id=repo_id)
    except Exception as e:
        logger.error("supabase_error", error=str(e), action="save_user_repo")

def get_chat_history(user_id: str, repo_id: str) -> list:
    """Fetches the chat history for a specific user and repository."""
    client = get_supabase_client()
    if not client:
        return []
        
    try:
        response = client.table("chat_history")\
            .select("*")\
            .eq("user_id", user_id)\
            .eq("repo_id", repo_id)\
            .order("created_at", desc=False)\
            .execute()
        return response.data
    except Exception as e:
        logger.error("supabase_error", error=str(e), action="get_chat_history")
        return []
