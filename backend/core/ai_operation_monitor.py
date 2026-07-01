"""Lightweight structured logging for AI-backed operations."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Iterator

from backend.core.logging import get_logger, log_event
from backend.core.logging.events import (
    AI_OPERATION_COMPLETED,
    AI_OPERATION_FAILED,
    AI_OPERATION_RESULT,
)

logger = get_logger("backend.ai_operations")


@contextmanager
def monitor_ai_operation(
    operation: str,
    *,
    project_id: int | None = None,
    generation_type: str | None = None,
    issue_code: str | None = None,
    attempt: int | None = None,
) -> Iterator[None]:
    """Log duration and failure shape for LLM/generation operations."""

    started = time.perf_counter()
    try:
        yield
    except Exception as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        log_event(
            logger,
            logging.WARNING,
            "ai_operation",
            AI_OPERATION_FAILED,
            "AI operation failed",
            operation=operation,
            project_id=project_id,
            generation_type=generation_type,
            issue_code=issue_code,
            attempt=attempt,
            duration_ms=duration_ms,
            error_type=type(exc).__name__,
        )
        raise
    else:
        duration_ms = int((time.perf_counter() - started) * 1000)
        log_event(
            logger,
            logging.INFO,
            "ai_operation",
            AI_OPERATION_COMPLETED,
            "AI operation completed",
            operation=operation,
            project_id=project_id,
            generation_type=generation_type,
            issue_code=issue_code,
            attempt=attempt,
            duration_ms=duration_ms,
        )


def log_ai_operation_result(
    operation: str,
    *,
    project_id: int | None = None,
    generation_type: str | None = None,
    issue_code: str | None = None,
    duration_ms: int | None = None,
    success_count: int | None = None,
    failure_count: int | None = None,
    status: str | None = None,
) -> None:
    """Log aggregate result data for batch AI operations."""

    log_event(
        logger,
        logging.INFO,
        "ai_operation",
        AI_OPERATION_RESULT,
        "AI operation result",
        operation=operation,
        project_id=project_id,
        generation_type=generation_type,
        issue_code=issue_code,
        duration_ms=duration_ms,
        success_count=success_count,
        failure_count=failure_count,
        status=status,
    )
