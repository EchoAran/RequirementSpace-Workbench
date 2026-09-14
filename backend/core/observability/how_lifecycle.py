from __future__ import annotations

import logging
import os

from backend.core.logging import get_logger, log_event

logger = get_logger("backend.how_lifecycle")


def emit_how_lifecycle_event(
    event: str,
    *,
    capability: str,
    project_id: int | None = None,
    workspace_id: int | None = None,
    flow_logical_uuid: str | None = None,
    correlation_id: str | None = None,
    error_code: str | None = None,
    level: int = logging.INFO,
    **metrics: int | str | bool | None,
) -> None:
    """Emit sanitized HOW lifecycle dimensions without business content."""
    log_event(
        logger,
        level,
        "how_lifecycle",
        event,
        "HOW lifecycle event",
        generation_backend=os.getenv(
            "REQUIREMENTSPACE_GENERATION_BACKEND",
            "legacy",
        ),
        capability=capability,
        project_id=project_id,
        workspace_id=workspace_id,
        flow_logical_uuid=flow_logical_uuid,
        correlation_id=correlation_id,
        error_code=error_code,
        **metrics,
    )
