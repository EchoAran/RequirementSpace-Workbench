"""Lightweight structured logging for AI-backed operations."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Iterator

logger = logging.getLogger("backend.ai_operations")


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
        logger.warning(
            "ai_operation_failed operation=%s project_id=%s generation_type=%s issue_code=%s "
            "attempt=%s duration_ms=%s error_type=%s",
            operation,
            project_id,
            generation_type,
            issue_code,
            attempt,
            duration_ms,
            type(exc).__name__,
        )
        raise
    else:
        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "ai_operation_completed operation=%s project_id=%s generation_type=%s issue_code=%s "
            "attempt=%s duration_ms=%s",
            operation,
            project_id,
            generation_type,
            issue_code,
            attempt,
            duration_ms,
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

    logger.info(
        "ai_operation_result operation=%s project_id=%s generation_type=%s issue_code=%s "
        "duration_ms=%s success_count=%s failure_count=%s status=%s",
        operation,
        project_id,
        generation_type,
        issue_code,
        duration_ms,
        success_count,
        failure_count,
        status,
    )
