"""
CodeLens Logger — Console + Persistent File Logging.

Every log event goes to TWO places simultaneously:
  1. Console   — colored, stage-tagged, human-readable output
  2. Log files — persistent storage you can review later:
       logs/codelens.log              (rolling daily, keeps 30 days)
       logs/runs/<repo>_<ts>.log        (one file per ingestion run)

Set LOG_FORMAT=json in your .env for structured JSON file output.
Set LOG_LEVEL=DEBUG in your .env for verbose per-chunk/batch logs.
"""

import io
import json
import logging
import logging.handlers
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import structlog

# ── Force UTF-8 output on Windows (avoids cp1252 UnicodeEncodeError) ─
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Log directory (relative to backend/) ─────────────────────────────
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
LOGS_DIR = _BACKEND_DIR / "logs"
RUNS_DIR = LOGS_DIR / "runs"

# ── ANSI Color Codes ──────────────────────────────────────────────────
RESET          = "\033[0m"
BOLD           = "\033[1m"
DIM            = "\033[2m"
WHITE          = "\033[37m"
YELLOW         = "\033[33m"
BRIGHT_RED     = "\033[91m"
BRIGHT_GREEN   = "\033[92m"
BRIGHT_YELLOW  = "\033[93m"
BRIGHT_BLUE    = "\033[94m"
BRIGHT_MAGENTA = "\033[95m"
BRIGHT_CYAN    = "\033[96m"
BRIGHT_WHITE   = "\033[97m"

STAGE_STYLES: dict[str, tuple[str, str]] = {
    "CLONE":    (BRIGHT_BLUE,    "CLONE   "),
    "FILTER":   (BRIGHT_CYAN,    "FILTER  "),
    "CHUNK":    (BRIGHT_YELLOW,  "CHUNK   "),
    "EMBED":    (BRIGHT_MAGENTA, "EMBED   "),
    "STORE":    (BRIGHT_GREEN,   "STORE   "),
    "RETRIEVE": (BRIGHT_CYAN,    "RETRIEVE"),
    "RERANK":   (BRIGHT_YELLOW,  "RERANK  "),
    "LLM":      (BRIGHT_MAGENTA, "LLM     "),
    "API":      (BRIGHT_BLUE,    "API     "),
    "SYSTEM":   (WHITE,          "SYSTEM  "),
    "ERROR":    (BRIGHT_RED,     "ERROR   "),
    "WARN":     (YELLOW,         "WARN    "),
}

LEVEL_COLORS = {
    "debug":    DIM + WHITE,
    "info":     BRIGHT_WHITE,
    "warning":  YELLOW,
    "error":    BRIGHT_RED,
    "critical": BOLD + BRIGHT_RED,
}


# ── Stage detection ───────────────────────────────────────────────────

def _detect_stage(event: str) -> str:
    """Infer which RAG pipeline stage a log event belongs to."""
    ev = event.lower()
    if any(k in ev for k in ("clone", "git", "reposit")):
        return "CLONE"
    if any(k in ev for k in ("filter", "discover", "file_walk", "walk")):
        return "FILTER"
    if any(k in ev for k in ("chunk", "ast", "parse", "split")):
        return "CHUNK"
    if any(k in ev for k in ("embed", "encod", "batch", "model_load", "embedding")):
        return "EMBED"
    if any(k in ev for k in ("store", "chroma", "vector", "collection", "insert")):
        return "STORE"
    if any(k in ev for k in ("retriev", "search", "query_embed")):
        return "RETRIEVE"
    if any(k in ev for k in ("rerank", "cross_enc", "score")):
        return "RERANK"
    if any(k in ev for k in ("llm", "groq", "generat", "token", "answer", "prompt")):
        return "LLM"
    if any(k in ev for k in ("error", "fail", "exception")):
        return "ERROR"
    if any(k in ev for k in ("warn",)):
        return "WARN"
    if any(k in ev for k in ("api", "request", "endpoint", "ingest_request", "query_request")):
        return "API"
    return "SYSTEM"


# ── Console renderer ──────────────────────────────────────────────────

def _console_renderer(logger, method, event_dict: dict) -> str:
    """Colored, stage-tagged, human-readable console output."""
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    level = event_dict.pop("level", "info").lower()
    event = event_dict.pop("event", "")

    stage = _detect_stage(event)
    color, stage_label = STAGE_STYLES.get(stage, (BRIGHT_WHITE, "OTHER   "))

    extras = "  ".join(
        f"{DIM}{k}{RESET}={BRIGHT_WHITE}{v}{RESET}"
        for k, v in event_dict.items()
        if k not in ("_record", "stack_info", "exc_info")
    )

    level_color = LEVEL_COLORS.get(level, WHITE)
    level_label = f"{level_color}{level.upper():<7}{RESET}"

    line = (
        f"{DIM}{ts}{RESET}  "
        f"{level_label}  "
        f"{color}{BOLD}[{stage_label.strip()}]{RESET}  "
        f"{color}{event}{RESET}"
    )
    if extras:
        line += f"  {extras}"
    return line


# ── File renderer (plain text, no ANSI codes) ─────────────────────────

def _file_renderer(logger, method, event_dict: dict) -> str:
    """Plain-text file output — no colors, readable in any text editor."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    level = event_dict.pop("level", "info").upper()
    event = event_dict.pop("event", "")
    stage = _detect_stage(event)

    # Remove internal structlog keys
    extras = "  ".join(
        f"{k}={v}"
        for k, v in event_dict.items()
        if k not in ("_record", "stack_info", "exc_info")
    )

    line = f"{ts}  {level:<7}  [{stage:<8}]  {event}"
    if extras:
        line += f"  |  {extras}"
    return line


# ── Dual-output handler setup ─────────────────────────────────────────

class _DualHandler(logging.Handler):
    """
    Routes every log record to two file handlers:
      1. The daily rolling log (logs/codelens_YYYY-MM-DD.log)
      2. The current per-run log (set via set_run_log_file)
    """
    def __init__(self):
        super().__init__()
        self._daily_handler: logging.handlers.TimedRotatingFileHandler | None = None
        self._run_handler: logging.FileHandler | None = None

    def setup_daily(self, logs_dir: Path, level: int):
        """Create or replace the daily rolling file handler."""
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = logs_dir / "codelens.log"
        h = logging.handlers.TimedRotatingFileHandler(
            filename=str(log_path),
            when="midnight",
            backupCount=30,
            encoding="utf-8",
        )
        h.setLevel(level)
        h.setFormatter(logging.Formatter("%(message)s"))
        self._daily_handler = h

    def set_run_log(self, run_log_path: Path):
        """Switch to a new per-run file handler (called at ingestion start)."""
        if self._run_handler:
            self._run_handler.close()
        run_log_path.parent.mkdir(parents=True, exist_ok=True)
        h = logging.FileHandler(str(run_log_path), encoding="utf-8")
        h.setFormatter(logging.Formatter("%(message)s"))
        self._run_handler = h

    def emit(self, record: logging.LogRecord):
        msg = self.format(record)
        if self._daily_handler:
            try:
                self._daily_handler.emit(record)
            except Exception:
                pass
        if self._run_handler:
            try:
                self._run_handler.emit(record)
            except Exception:
                pass


# ── Global dual handler instance ──────────────────────────────────────
_dual_handler = _DualHandler()


def set_run_log_file(repo_id: str) -> Path:
    """
    Call this at the start of each ingestion run to create a dedicated log file.

    Args:
        repo_id: e.g. "santhoshkumars2004/CodeLens"

    Returns:
        Path to the run log file that was created.
    """
    safe_repo = repo_id.replace("/", "_").replace(" ", "_")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    run_log_path = RUNS_DIR / f"ingestion_{safe_repo}_{ts}.log"
    _dual_handler.set_run_log(run_log_path)
    return run_log_path


# ── File-output structlog processor chain ─────────────────────────────

def _build_file_processors():
    return [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        _file_renderer,
    ]


# ── Public setup ──────────────────────────────────────────────────────

_logging_configured = False


def setup_logging(log_level: str = "INFO") -> None:
    """
    Configure all logging for CodeLens.
    """
    global _logging_configured
    if _logging_configured:
        return

    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    use_json = os.getenv("LOG_FORMAT", "pretty").lower() == "json"

    # 1. Configure structlog to use stdlib
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # 2. Configure stdlib handlers
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    root_logger.handlers.clear()

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    if use_json:
        console_formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
        )
    else:
        console_formatter = structlog.stdlib.ProcessorFormatter(
            processor=_console_renderer,
        )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File Handlers (Dual Handler)
    _dual_handler.setup_daily(LOGS_DIR, numeric_level)
    file_formatter = structlog.stdlib.ProcessorFormatter(
        processor=_file_renderer,
    )
    _dual_handler.setFormatter(file_formatter)
    root_logger.addHandler(_dual_handler)

    _logging_configured = True


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get a named structured logger.
    """
    return structlog.get_logger(name)


def get_file_logger(name: str) -> logging.Logger:
    """
    Get a plain stdlib logger that writes ONLY to the log files (not console).
    """
    lg = logging.getLogger(f"codelens.file.{name}")
    lg.propagate = False
    if not lg.handlers:
        lg.addHandler(_dual_handler)
    return lg
