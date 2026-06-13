"""
StackSense Structured Logging Module.

Configures structured logging using structlog for consistent,
JSON-formatted log output across the entire application.
"""

import logging
import sys

import structlog


def setup_logging(log_level: str = "INFO") -> None:
    """
    Configure structured logging for the application.

    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    # Set the numeric log level
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Configure structlog processors
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Also configure standard library logging to work with structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=numeric_level,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get a named structured logger instance.

    Args:
        name: Logger name, typically __name__ of the calling module.

    Returns:
        A bound structlog logger.
    """
    return structlog.get_logger(name)
