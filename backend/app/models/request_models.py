"""
StackSense Pydantic Request Models.

Defines the schema for all incoming API request payloads.
"""

from pydantic import BaseModel, Field, HttpUrl
from typing import Optional


class IngestRequest(BaseModel):
    """Request to ingest/index a GitHub repository."""
    repo_url: str = Field(
        ...,
        description="GitHub repository URL to clone and index",
        examples=["https://github.com/fastapi/fastapi"],
    )
    branch: Optional[str] = Field(
        default=None,
        description="Specific branch to clone (defaults to repo default branch)",
    )


class QueryRequest(BaseModel):
    """Request to query an indexed repository."""
    repo_id: str = Field(
        ...,
        description="Repository identifier (owner/repo format)",
        examples=["fastapi/fastapi"],
    )
    question: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Natural language question about the codebase",
        examples=["How does authentication work?"],
    )
    top_k: Optional[int] = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of relevant chunks to retrieve",
    )
    language_filter: Optional[str] = Field(
        default=None,
        description="Restrict search to a specific language (e.g. 'python', 'typescript')",
        examples=["python"],
    )
    path_filter: Optional[str] = Field(
        default=None,
        description="Restrict search to files whose path contains this string (e.g. 'backend/api')",
        examples=["backend/api"],
    )

