"""
CodeLens Configuration Module.

Centralizes all environment variables and application settings
using Pydantic Settings for validation and type safety.
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ── Application ──────────────────────────────────────────────
    app_name: str = "CodeLens"
    app_version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"

    # ── Backend Server ───────────────────────────────────────────
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    frontend_url: str = "http://localhost:3000"

    # ── Groq LLM (Free Tier) ────────────────────────────────────
    groq_api_key: str = ""
    groq_model: str = "llama3-8b-8192"
    groq_temperature: float = 0.1
    groq_max_tokens: int = 2048

    # ── ChromaDB (Local Vector DB) ──────────────────────────────
    chroma_host: str = "localhost"
    chroma_port: int = 8001
    chroma_persist_dir: str = "./data/chromadb"

    # ── HuggingFace Embeddings (Local, Free) ────────────────────
    embedding_model: str = "BAAI/bge-base-en-v1.5"
    embedding_batch_size: int = 32

    # ── Reranker Model ──────────────────────────────────────────
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-12-v2"
    reranker_top_k: int = 5

    # ── GitHub ──────────────────────────────────────────────────
    github_token: Optional[str] = None
    repos_dir: str = "/tmp/codelens_repos"

    # ── AWS S3 (Free Tier) ──────────────────────────────────────
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "us-east-1"
    s3_bucket_name: str = "codelens-metadata"

    # ── LangFuse (LLM Tracing) ──────────────────────────────────
    langfuse_public_key: Optional[str] = None
    langfuse_secret_key: Optional[str] = None
    langfuse_host: str = "http://localhost:3002"

    # ── Supabase (Database) ─────────────────────────────────────
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None

    # ── Limits ──────────────────────────────────────────────────
    max_repo_size_mb: int = 500
    max_files_per_repo: int = 10000
    retriever_top_k: int = 20
    chunk_lines: int = 60        # sliding-window chunk size in lines
    chunk_overlap_lines: int = 10  # overlap between consecutive sliding-window chunks

    @property
    def repos_path(self) -> Path:
        """Get the absolute path for cloned repositories."""
        return Path(self.repos_dir)

    @property
    def chroma_persist_path(self) -> Path:
        """Get the absolute path for ChromaDB persistence."""
        return Path(self.chroma_persist_dir)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "allow"


@lru_cache()
def get_settings() -> Settings:
    """
    Returns a cached singleton instance of Settings.
    Uses lru_cache to avoid re-reading .env on every call.
    """
    return Settings()
