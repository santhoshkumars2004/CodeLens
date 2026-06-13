"""
StackSense Code Chunker.

Intelligent code chunking that uses AST parsing for Python files
and falls back to token-based overlapping chunks for other languages.
Each chunk preserves file path, line numbers, and language metadata.
"""

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CodeChunk:
    """Represents a chunk of code with metadata."""
    content: str
    file_path: str
    start_line: int
    end_line: int
    language: str
    chunk_type: str = "generic"  # "function", "class", "module", "generic"
    name: Optional[str] = None  # Function/class name if applicable
    metadata: dict = field(default_factory=dict)

    @property
    def token_count(self) -> int:
        """Approximate token count (words * 1.3)."""
        return int(len(self.content.split()) * 1.3)


def chunk_python_file(content: str, file_path: str) -> List[CodeChunk]:
    """
    Chunk a Python file by function and class definitions using AST.
    Falls back to generic chunking if AST parsing fails.
    """
    try:
        tree = ast.parse(content)
    except SyntaxError:
        logger.debug("ast_parse_failed", file=file_path)
        return chunk_by_lines(content, file_path, "python")

    lines = content.splitlines()
    chunks = []
    used_lines = set()

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = node.lineno - 1
            end = node.end_lineno if node.end_lineno else start + 1
            chunk_content = "\n".join(lines[start:end])

            if len(chunk_content.strip()) > 20:
                chunks.append(CodeChunk(
                    content=chunk_content,
                    file_path=file_path,
                    start_line=node.lineno,
                    end_line=end,
                    language="python",
                    chunk_type="function",
                    name=node.name,
                ))
                used_lines.update(range(start, end))

        elif isinstance(node, ast.ClassDef):
            start = node.lineno - 1
            end = node.end_lineno if node.end_lineno else start + 1
            chunk_content = "\n".join(lines[start:end])

            if len(chunk_content.strip()) > 20:
                chunks.append(CodeChunk(
                    content=chunk_content,
                    file_path=file_path,
                    start_line=node.lineno,
                    end_line=end,
                    language="python",
                    chunk_type="class",
                    name=node.name,
                ))
                used_lines.update(range(start, end))

    # Capture module-level code (imports, constants, etc.)
    module_lines = []
    module_start = None
    for i, line in enumerate(lines):
        if i not in used_lines:
            if module_start is None:
                module_start = i
            module_lines.append(line)
        else:
            if module_lines and len("\n".join(module_lines).strip()) > 20:
                chunks.append(CodeChunk(
                    content="\n".join(module_lines),
                    file_path=file_path,
                    start_line=(module_start or 0) + 1,
                    end_line=i,
                    language="python",
                    chunk_type="module",
                ))
            module_lines = []
            module_start = None

    # Remaining module-level code at end of file
    if module_lines and len("\n".join(module_lines).strip()) > 20:
        chunks.append(CodeChunk(
            content="\n".join(module_lines),
            file_path=file_path,
            start_line=(module_start or 0) + 1,
            end_line=len(lines),
            language="python",
            chunk_type="module",
        ))

    return chunks if chunks else chunk_by_lines(content, file_path, "python")


def chunk_js_ts_file(content: str, file_path: str, language: str) -> List[CodeChunk]:
    """
    Chunk JavaScript/TypeScript files by function blocks using regex.
    Handles: function declarations, arrow functions, class methods.
    """
    chunks = []
    lines = content.splitlines()

    # Patterns for JS/TS function detection
    patterns = [
        r'(?:export\s+)?(?:async\s+)?function\s+(\w+)',
        r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(',
        r'(?:export\s+)?class\s+(\w+)',
    ]

    boundaries = []
    for i, line in enumerate(lines):
        for pattern in patterns:
            match = re.match(pattern, line.strip())
            if match:
                boundaries.append((i, match.group(1)))
                break

    if not boundaries:
        return chunk_by_lines(content, file_path, language)

    for idx, (start, name) in enumerate(boundaries):
        end = boundaries[idx + 1][0] if idx + 1 < len(boundaries) else len(lines)
        chunk_content = "\n".join(lines[start:end]).rstrip()

        if len(chunk_content.strip()) > 20:
            chunks.append(CodeChunk(
                content=chunk_content,
                file_path=file_path,
                start_line=start + 1,
                end_line=end,
                language=language,
                chunk_type="function",
                name=name,
            ))

    # Capture header (imports, etc.)
    if boundaries and boundaries[0][0] > 0:
        header = "\n".join(lines[:boundaries[0][0]])
        if len(header.strip()) > 20:
            chunks.insert(0, CodeChunk(
                content=header,
                file_path=file_path,
                start_line=1,
                end_line=boundaries[0][0],
                language=language,
                chunk_type="module",
            ))

    return chunks if chunks else chunk_by_lines(content, file_path, language)


def chunk_by_lines(
    content: str,
    file_path: str,
    language: str,
    chunk_size: int = 60,
    overlap: int = 10,
) -> List[CodeChunk]:
    """
    Generic line-based chunking with overlap.
    Used as fallback when language-specific parsing isn't available.
    """
    lines = content.splitlines()
    chunks = []

    if len(lines) <= chunk_size:
        return [CodeChunk(
            content=content,
            file_path=file_path,
            start_line=1,
            end_line=len(lines),
            language=language,
            chunk_type="generic",
        )]

    start = 0
    while start < len(lines):
        end = min(start + chunk_size, len(lines))
        chunk_content = "\n".join(lines[start:end])

        if len(chunk_content.strip()) > 20:
            chunks.append(CodeChunk(
                content=chunk_content,
                file_path=file_path,
                start_line=start + 1,
                end_line=end,
                language=language,
                chunk_type="generic",
            ))

        start += chunk_size - overlap

    return chunks


def chunk_file(content: str, file_path: str, language: str) -> List[CodeChunk]:
    """
    Main entry point: chunk a file based on its language.
    """
    if not content or not content.strip():
        return []

    if language == "python":
        return chunk_python_file(content, file_path)
    elif language in ("javascript", "typescript"):
        return chunk_js_ts_file(content, file_path, language)
    else:
        return chunk_by_lines(content, file_path, language)
