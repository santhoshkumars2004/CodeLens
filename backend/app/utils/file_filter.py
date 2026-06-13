"""
StackSense File Filter Utility.

Determines which files should be included or skipped during
repository indexing.
"""

import os
from pathlib import Path
from typing import List, Set

from app.utils.logger import get_logger

logger = get_logger(__name__)

SKIP_DIRECTORIES: Set[str] = {
    "node_modules", ".git", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", "dist", "build", ".next", "out", ".vercel", ".venv",
    "venv", "env", ".tox", ".eggs", "egg-info", ".idea", ".vscode",
    ".gradle", "target", "vendor", "coverage", ".nyc_output", ".cache",
    ".turbo", ".svn", ".hg", "bower_components",
}

SKIP_EXTENSIONS: Set[str] = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".webp",
    ".mp4", ".mp3", ".avi", ".mov", ".wav",
    ".zip", ".tar", ".gz", ".rar", ".7z",
    ".exe", ".dll", ".so", ".dylib", ".class", ".o", ".pyc", ".wasm",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".lock", ".db", ".sqlite", ".sqlite3", ".map",
}

SKIP_FILENAMES: Set[str] = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "Pipfile.lock", "poetry.lock", ".DS_Store",
}

SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".py": "python", ".js": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".java": "java",
    ".go": "go", ".rs": "rust", ".rb": "ruby", ".php": "php",
    ".c": "c", ".cpp": "cpp", ".h": "c", ".hpp": "cpp",
    ".cs": "csharp", ".swift": "swift", ".kt": "kotlin",
    ".scala": "scala", ".sql": "sql", ".sh": "shell",
    ".yaml": "yaml", ".yml": "yaml", ".json": "json",
    ".xml": "xml", ".html": "html", ".css": "css",
    ".scss": "scss", ".md": "markdown", ".toml": "toml",
    ".ini": "ini", ".tf": "terraform", ".proto": "protobuf",
    ".graphql": "graphql", ".vue": "vue", ".svelte": "svelte",
}

MAX_FILE_SIZE_BYTES = 1_000_000


def should_skip_directory(dir_name: str) -> bool:
    """Check if a directory should be skipped."""
    return dir_name in SKIP_DIRECTORIES or dir_name.startswith(".")


def should_skip_file(file_path: Path) -> bool:
    """Check if a file should be skipped during indexing."""
    if file_path.name in SKIP_FILENAMES:
        return True
    if file_path.suffix.lower() in SKIP_EXTENSIONS:
        return True
    try:
        size = file_path.stat().st_size
        if size > MAX_FILE_SIZE_BYTES or size == 0:
            return True
    except OSError:
        return True
    return False


def detect_language(file_path: Path) -> str:
    """Detect the programming language from file extension."""
    if file_path.name.lower() in ("dockerfile", "containerfile"):
        return "dockerfile"
    if file_path.name.lower() in ("makefile",):
        return "makefile"
    return SUPPORTED_EXTENSIONS.get(file_path.suffix.lower(), "unknown")


def get_code_files(repo_path: Path, max_files: int = 10000) -> List[dict]:
    """
    Walk a repository and return all indexable code files.

    Returns list of dicts: {path, relative_path, language, size_bytes}
    """
    code_files = []

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if not should_skip_directory(d)]

        for filename in files:
            if len(code_files) >= max_files:
                logger.warning("max_files_reached", max_files=max_files)
                return code_files

            file_path = Path(root) / filename
            if should_skip_file(file_path):
                continue

            relative_path = file_path.relative_to(repo_path)
            code_files.append({
                "path": str(file_path),
                "relative_path": str(relative_path),
                "language": detect_language(file_path),
                "size_bytes": file_path.stat().st_size,
            })

    logger.info("code_files_discovered", total=len(code_files))
    return code_files
