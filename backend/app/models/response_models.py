"""
StackSense Pydantic Response Models.

Defines the schema for all API response payloads.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class CitedChunk(BaseModel):
    """A code chunk cited as evidence in the answer."""
    file_path: str = Field(description="Relative file path in the repo")
    start_line: int = Field(description="Starting line number")
    end_line: int = Field(description="Ending line number")
    content: str = Field(description="Code snippet content")
    language: str = Field(description="Programming language")
    relevance_score: float = Field(description="Relevance score (0-1)")


class QueryResponse(BaseModel):
    """Response from a codebase query."""
    answer: str = Field(description="Generated answer with code references")
    citations: List[CitedChunk] = Field(description="Source code citations")
    confidence_score: float = Field(
        description="Overall confidence (0-1)", ge=0, le=1
    )
    query: str = Field(description="Original question")
    repo_id: str = Field(description="Repository identifier")
    latency_ms: float = Field(description="Total processing time in ms")


class IngestResponse(BaseModel):
    """Response from repository ingestion."""
    repo_id: str = Field(description="Repository identifier")
    status: str = Field(description="Ingestion status")
    files_indexed: int = Field(description="Number of files indexed")
    chunks_created: int = Field(description="Number of chunks stored")
    languages: List[str] = Field(description="Languages detected")
    duration_seconds: float = Field(description="Time taken to ingest")
    message: str = Field(description="Status message")


class RepoInfo(BaseModel):
    """Information about an indexed repository."""
    repo_id: str
    repo_url: str
    files_indexed: int
    chunks_count: int
    languages: List[str]
    indexed_at: str
    status: str


class RepoListResponse(BaseModel):
    """Response listing all indexed repositories."""
    repos: List[RepoInfo]
    total: int


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    version: str
    chromadb_connected: bool
    timestamp: str
