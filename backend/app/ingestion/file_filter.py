"""
CodeLens — File Filter (app/ingestion/file_filter.py)

Walks a cloned repository and decides which files are worth indexing.
Every skipped file is logged at DEBUG level with a clear reason.
"""

import json
import os
from collections import defaultdict
from pathlib import Path
from typing import List, Set, Dict

from app.utils.logger import get_logger

logger = get_logger(__name__)


# ── Directories — never recurse into these ────────────────────────────
SKIP_DIRECTORIES: Set[str] = {
    "local_model",
    "node_modules",
    "__pycache__",
    ".git",
    "dist",
    "build",
    ".venv",
    "venv",
    "env",
    ".next",
    "coverage",
    "chroma_data",
    "data",
    # Additional common noise dirs
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "out",
    ".vercel",
    ".tox",
    ".eggs",
    "egg-info",
    ".idea",
    ".vscode",
    ".gradle",
    "target",
    "vendor",
    ".nyc_output",
    ".cache",
    ".turbo",
    ".svn",
    ".hg",
    "bower_components",
    # Data dumps and test fixtures
    "fixtures",
    "__fixtures__",
    "mocks",
    "__mocks__",
    "test_data",
}

# ── File extensions to skip ───────────────────────────────────────────
SKIP_EXTENSIONS: Set[str] = {
    # Text / config / data (not source code)
    ".txt",
    ".lock",
    ".csv",
    ".log",
    ".env",
    # Binary model weights
    ".bin",
    ".pt",
    ".onnx",
    ".pkl",
    ".npz",
    ".npy",
    ".h5",
    ".safetensors",
    # Images / media
    ".png",
    ".jpg",
    ".jpeg",
    ".svg",
    ".gif",
    ".ico",
    ".webp",
    ".bmp",
    ".mp4",
    ".mp3",
    ".avi",
    ".mov",
    ".wav",
    # Archives / compiled
    ".zip",
    ".tar",
    ".gz",
    ".rar",
    ".7z",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".class",
    ".o",
    ".pyc",
    ".wasm",
    # Fonts
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".otf",
    # Documents
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    # Build artifacts
    ".map",
    ".db",
    ".sqlite",
    ".sqlite3",
}

# ── Specific filenames — always skip regardless of extension ──────────
SKIP_FILENAMES: Set[str] = {
    # Tokenizer / model config files
    "vocab.txt",
    "tokenizer.json",
    "tokenizer_config.json",
    "config.json",
    "special_tokens_map.json",
    # Package manager lockfiles
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "Pipfile.lock",
    "poetry.lock",
    # System
    ".DS_Store",
}

# ── File size limits ──────────────────────────────────────────────────
MIN_FILE_SIZE_BYTES = 100           # Skip near-empty files
MAX_FILE_SIZE_BYTES = 500 * 1024    # 500 KB — larger files are usually not source code

# ── Source code extensions we DO want to index ────────────────────────
SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".py":      "python",
    ".js":      "javascript",
    ".jsx":     "javascript",
    ".ts":      "typescript",
    ".tsx":     "typescript",
    ".java":    "java",
    ".go":      "go",
    ".rs":      "rust",
    ".rb":      "ruby",
    ".php":     "php",
    ".c":       "c",
    ".cpp":     "cpp",
    ".h":       "c",
    ".hpp":     "cpp",
    ".cs":      "csharp",
    ".swift":   "swift",
    ".kt":      "kotlin",
    ".scala":   "scala",
    ".sql":     "sql",
    ".sh":      "shell",
    ".bash":    "shell",
    ".zsh":     "shell",
    ".tf":      "terraform",
    ".proto":   "protobuf",
    ".graphql": "graphql",
    ".vue":     "vue",
    ".svelte":  "svelte",
    ".html":    "html",
    ".css":     "css",
    ".scss":    "scss",
    ".toml":    "toml",
    ".ini":     "ini",
    ".xml":     "xml",
    # Config & Documentation
    ".json":    "json",
    ".yaml":    "yaml",
    ".yml":     "yaml",
    ".md":      "markdown",
}

# Extension-less filenames we allow through
ALLOWED_NO_EXTENSION: Set[str] = {
    "dockerfile",
    "containerfile",
    "makefile",
    "jenkinsfile",
}


# ── Public API ────────────────────────────────────────────────────────

def should_skip_directory(dir_name: str) -> bool:
    """
    Return True if an entire directory should be excluded during the walk.

    Args:
        dir_name: The directory name (not its full path).

    Returns:
        True if the directory should be skipped.
    """
    if dir_name in SKIP_DIRECTORIES:
        logger.debug(f"Skipping directory '{dir_name}' — reason: in SKIP_DIRECTORIES")
        return True
    if dir_name.startswith("."):
        logger.debug(f"Skipping directory '{dir_name}' — reason: starts with '.'")
        return True
    return False


def should_skip_file(file_path: str, file_size_bytes: int) -> bool:
    """
    Return True if a file should be excluded from indexing.

    Delegates to _skip_reason() which is the single source of truth
    so skip logic is never duplicated.
    """
    reason = _skip_reason(file_path, file_size_bytes)
    if reason:
        logger.debug(f"Skipping {file_path} — reason: {reason}")
        return True
    return False


def detect_language(file_path: str) -> str:
    """
    Return the programming language for a file based on its extension/name.

    Args:
        file_path: Path to the file.

    Returns:
        Language name string (e.g. 'python', 'typescript') or 'unknown'.
    """
    p = Path(file_path)
    name = p.name.lower()
    ext = p.suffix.lower()

    if name in ("dockerfile", "containerfile"):
        return "dockerfile"
    if name == "makefile":
        return "makefile"
    if name == "jenkinsfile":
        return "groovy"

    return SUPPORTED_EXTENSIONS.get(ext, "unknown")


def get_code_files(
    repo_path: Path,
    max_files: int = 10_000,
    manifest_path: Path | None = None,
) -> List[dict]:
    """
    Walk a repository and return all indexable source code files.

    Applies every skip rule (directory, extension, filename, size) and
    logs a summary at INFO level when done.

    Also writes a "skip manifest" JSON file (if manifest_path is given)
    so the query pipeline can explain WHY a file was not indexed when
    a user asks about it.

    Args:
        repo_path: Root path of the cloned repository.
        max_files: Hard cap on the number of files returned.
        manifest_path: Optional path to write the skip manifest JSON.

    Returns:
        List of dicts with keys: path, relative_path, language, size_bytes.
    """
    code_files: List[dict] = []
    lang_counts: dict = defaultdict(int)
    skipped_count = 0
    # skip_manifest maps relative_path → human-readable skip reason
    skip_manifest: Dict[str, str] = {}

    logger.info("filter_walking_repo", path=str(repo_path))

    for root, dirs, files in os.walk(repo_path):
        # Prune directories in-place so os.walk won't recurse into them
        dirs[:] = [d for d in dirs if not should_skip_directory(d)]

        for filename in files:
            if len(code_files) >= max_files:
                logger.warning(
                    "filter_max_files_reached",
                    max_files=max_files,
                    indexed=len(code_files),
                    skipped=skipped_count,
                )
                return code_files

            file_path = Path(root) / filename
            relative_path = str(file_path.relative_to(repo_path))

            try:
                size = file_path.stat().st_size
            except OSError as exc:
                reason = f"Cannot read file ({exc})"
                logger.debug(f"Skipping {relative_path} — reason: {reason}")
                skip_manifest[relative_path] = reason
                skipped_count += 1
                continue

            skip_reason = _skip_reason(str(file_path), size)
            if skip_reason:
                skip_manifest[relative_path] = skip_reason
                skipped_count += 1
                continue

            language = detect_language(str(file_path))
            code_files.append({
                "path": str(file_path),
                "relative_path": relative_path,
                "language": language,
                "size_bytes": size,
            })
            lang_counts[language] += 1

    lang_summary = "  ".join(
        f"{lang}:{count}"
        for lang, count in sorted(lang_counts.items(), key=lambda x: -x[1])
    )

    logger.info(
        "filter_complete",
        total_indexed=len(code_files),
        total_skipped=skipped_count,
        languages=lang_summary or "none",
    )

    # Write the skip manifest so queries can detect filtered files
    if manifest_path is not None:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(skip_manifest, f, indent=2)
        logger.info(
            "skip_manifest_saved",
            path=str(manifest_path),
            skipped_files=len(skip_manifest),
        )

    return code_files


def _skip_reason(file_path: str, file_size_bytes: int) -> str | None:
    """
    Return the human-readable skip reason for a file, or None if it should be indexed.
    This is the single source of truth used by both should_skip_file() and the manifest.
    """
    p = Path(file_path)
    name = p.name
    ext = p.suffix.lower()

    if name in SKIP_FILENAMES:
        return f"Filename '{name}' is explicitly excluded (tokenizer/lockfile/config)"
    if ext in SKIP_EXTENSIONS:
        return (
            f"Extension '{ext}' is excluded — "
            + {
                ".txt": "Plain text files are not indexed",
                ".log": "Log files are not indexed",
                ".env": ".env files contain secrets and are not indexed",
                ".bin": "Binary model weight file",
                ".pt": "PyTorch model weight file",
            }.get(ext, "non-source file type")
        )
    if ext not in SUPPORTED_EXTENSIONS and name.lower() not in ALLOWED_NO_EXTENSION:
        return f"Extension '{ext}' is not in the supported source-code list"
    if file_size_bytes < MIN_FILE_SIZE_BYTES:
        return f"File is too small ({file_size_bytes} bytes) — likely empty or auto-generated"
    if file_size_bytes > MAX_FILE_SIZE_BYTES:
        return (
            f"File is too large ({file_size_bytes:,} bytes > {MAX_FILE_SIZE_BYTES:,} byte limit) "
            "— likely a generated or bundled file"
        )
    return None
