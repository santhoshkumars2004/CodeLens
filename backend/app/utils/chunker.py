"""
CodeLens Code Chunker (app/utils/chunker.py)

Splits code files into semantically meaningful chunks, then wraps each
chunk in a context header so the embedding model can answer questions like
"what does embedding_service.py do?" by connecting the query to the right file.

Three chunking strategies:
  - Python    → AST-based (one chunk per function / class / module-level block)
  - JS / TS   → Regex-based (one chunk per exported function / class)
  - All else  → Overlapping sliding window (60-line chunks, 10-line overlap)

Every chunk's document string starts with:
  File: <path>
  Language: <language>
  Function: <name>

  <code content>

This context header is critical — without it the embedding model cannot
connect "which file does X?" questions to the correct chunks in ChromaDB.
"""

import ast
import re
from typing import List

from app.utils.logger import get_logger

logger = get_logger(__name__)

# ── Sliding-window defaults ────────────────────────────────────────────
CHUNK_SIZE = 60   # lines
OVERLAP    = 10   # lines


# ── Context header builder ─────────────────────────────────────────────

def _make_document(
    file_path: str,
    language: str,
    name: str,
    code_content: str,
) -> str:
    """
    Prepend the context header to raw code so the embedding model
    knows which file and which symbol this chunk belongs to.
    """
    return (
        f"File: {file_path}\n"
        f"Language: {language}\n"
        f"Function: {name}\n\n"
        f"{code_content}"
    )


def _make_chunk(
    file_path: str,
    language: str,
    name: str,
    code_content: str,
    start_line: int,
    end_line: int,
    chunk_type: str,
) -> dict:
    """
    Build the canonical chunk dict used throughout the pipeline.

    Returns:
        {
          "document": "<context header>\n\n<code>",
          "metadata": { file_path, start_line, end_line, language,
                        chunk_type, chunk_name }
        }
    """
    return {
        "document": _make_document(file_path, language, name, code_content),
        "metadata": {
            "file_path":  file_path,
            "start_line": start_line,
            "end_line":   end_line,
            "language":   language,
            "chunk_type": chunk_type,
            "chunk_name": name,
        },
    }


# ── Python AST chunker ────────────────────────────────────────────────

def _chunk_python(content: str, file_path: str) -> List[dict]:
    """
    Chunk a Python file using its AST.

    Strategy:
    - Each top-level FunctionDef / AsyncFunctionDef → one chunk (type: function)
    - Each top-level ClassDef (including all its methods) → one chunk (type: class)
    - All remaining module-level statements → one "module-level" chunk (type: module)
    - Falls back to sliding-window if the file has a SyntaxError
    """
    try:
        tree = ast.parse(content)
    except SyntaxError as exc:
        logger.debug(f"Skipping AST for {file_path} — SyntaxError: {exc}")
        return _chunk_sliding_window(content, file_path, "python")

    lines      = content.splitlines()
    chunks: List[dict] = []
    covered_lines: set = set()

    # Only process TOP-LEVEL nodes (direct children of the Module)
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue

        start      = node.lineno          # 1-indexed
        end        = node.end_lineno      # 1-indexed
        name       = node.name
        chunk_type = "class" if isinstance(node, ast.ClassDef) else "function"
        code       = "\n".join(lines[start - 1 : end])

        if not code.strip():
            continue

        covered_lines.update(range(start, end + 1))
        chunks.append(_make_chunk(file_path, "python", name, code, start, end, chunk_type))
        logger.debug(f"chunk_ast_node  {chunk_type:<8} {name}  lines {start}-{end}  file={file_path}")

    # Collect module-level code (imports, constants, etc.) that wasn't covered
    module_lines = [
        (i + 1, line)
        for i, line in enumerate(lines)
        if (i + 1) not in covered_lines
    ]
    if module_lines:
        module_code = "\n".join(l for _, l in module_lines)
        if module_code.strip():
            start_l = module_lines[0][0]
            end_l   = module_lines[-1][0]
            chunks.insert(0, _make_chunk(
                file_path, "python", "module-level",
                module_code, start_l, end_l, "module",
            ))
            logger.debug(f"chunk_ast_node  module   module-level  lines {start_l}-{end_l}  file={file_path}")

    if not chunks:
        logger.debug(f"No AST nodes found in {file_path}, falling back to sliding window")
        return _chunk_sliding_window(content, file_path, "python")

    return chunks


# ── JavaScript / TypeScript regex chunker ─────────────────────────────

def _chunk_js_ts(content: str, file_path: str, language: str) -> List[dict]:
    """
    Chunk a JS/TS file by detected function / class boundaries using regex.

    Detected patterns (matched at start of a line after stripping):
    - function declarations:    function foo() / async function foo()
    - arrow-function variables: const foo = () => / const foo = async () =>
    - class declarations:       class Foo / export class Foo
    - export default:           export default function
    """
    lines = content.splitlines()
    chunks: List[dict] = []

    # Patterns: (regex, chunk_type)
    PATTERNS = [
        (r"(?:export\s+)?(?:async\s+)?function\s+(\w+)",           "function"),
        (r"(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(", "function"),
        (r"(?:export\s+default\s+(?:async\s+)?function)\s*(\w*)",  "function"),
        (r"(?:export\s+)?(?:default\s+)?class\s+(\w+)",            "class"),
    ]

    boundaries: List[tuple] = []   # (line_index_0based, name, chunk_type)
    for i, line in enumerate(lines):
        stripped = line.strip()
        for pattern, ctype in PATTERNS:
            m = re.match(pattern, stripped)
            if m:
                name = m.group(1) if m.lastindex and m.group(1) else f"anonymous_{i+1}"
                boundaries.append((i, name, ctype))
                break

    if not boundaries:
        return _chunk_sliding_window(content, file_path, language)

    # Everything before the first boundary → module chunk (imports, etc.)
    if boundaries[0][0] > 0:
        header_code = "\n".join(lines[: boundaries[0][0]])
        if header_code.strip():
            chunks.append(_make_chunk(
                file_path, language, "module-level",
                header_code, 1, boundaries[0][0], "module",
            ))

    # One chunk per detected boundary
    for idx, (start, name, ctype) in enumerate(boundaries):
        end_0 = boundaries[idx + 1][0] if idx + 1 < len(boundaries) else len(lines)
        code   = "\n".join(lines[start : end_0]).rstrip()

        if len(code.strip()) > 20:
            chunks.append(_make_chunk(
                file_path, language, name,
                code, start + 1, end_0, ctype,
            ))
            logger.debug(f"chunk_js_node  {ctype:<8} {name}  lines {start+1}-{end_0}  file={file_path}")

    return chunks if chunks else _chunk_sliding_window(content, file_path, language)


# ── Sliding-window fallback ────────────────────────────────────────────

def _chunk_sliding_window(
    content: str,
    file_path: str,
    language: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = OVERLAP,
) -> List[dict]:
    """
    Generic overlapping sliding-window chunker.
    Used for all languages without a dedicated parser, and as fallback.

    chunk_size = 60 lines, overlap = 10 lines.
    chunk_name = "lines-{start}-{end}"
    """
    lines = content.splitlines()

    # Short file fits in a single chunk
    if len(lines) <= chunk_size:
        name = f"lines-1-{len(lines)}"
        return [_make_chunk(file_path, language, name, content, 1, len(lines), "block")]

    chunks: List[dict] = []
    start = 0
    while start < len(lines):
        end  = min(start + chunk_size, len(lines))
        code = "\n".join(lines[start : end])
        name = f"lines-{start + 1}-{end}"

        if len(code.strip()) > 20:
            chunks.append(_make_chunk(
                file_path, language, name,
                code, start + 1, end, "block",
            ))

        start += chunk_size - overlap

    return chunks


# ── Public API ────────────────────────────────────────────────────────

def chunk_file(content: str, file_path: str, language: str) -> List[dict]:
    """
    Main entry point — chunk a file using the best strategy for its language.

    Returns:
        List of chunk dicts, each with keys "document" and "metadata".
        The "document" value has the context header prepended so ChromaDB
        stores it with the full File/Language/Function context.
    """
    if not content or not content.strip():
        return []

    if language == "python":
        result = _chunk_python(content, file_path)
    elif language in ("javascript", "typescript"):
        result = _chunk_js_ts(content, file_path, language)
    else:
        result = _chunk_sliding_window(content, file_path, language)

    logger.debug(
        f"chunk_file_done  file={file_path}  language={language}  chunks={len(result)}"
    )
    return result


# ── Backward-compat shim (old callers used CodeChunk dataclass) ────────

class CodeChunk:
    """
    Thin shim for code that still calls chunk_file() and expects a
    CodeChunk-like object. New code should use the dict return directly.
    """
    __slots__ = ("content", "file_path", "start_line", "end_line",
                 "language", "chunk_type", "name", "document")

    def __init__(self, chunk_dict: dict):
        meta             = chunk_dict["metadata"]
        self.document    = chunk_dict["document"]
        self.content     = chunk_dict["document"]          # full doc including header
        self.file_path   = meta["file_path"]
        self.start_line  = meta["start_line"]
        self.end_line    = meta["end_line"]
        self.language    = meta["language"]
        self.chunk_type  = meta["chunk_type"]
        self.name        = meta["chunk_name"]

    @property
    def token_count(self) -> int:
        return int(len(self.content.split()) * 1.3)


def chunk_file_as_objects(content: str, file_path: str, language: str) -> List[CodeChunk]:
    """Return chunks as CodeChunk objects instead of dicts (legacy compat)."""
    return [CodeChunk(c) for c in chunk_file(content, file_path, language)]
