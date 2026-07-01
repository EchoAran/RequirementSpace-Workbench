from __future__ import annotations

import logging

from backend.core.logging.config import load_logging_settings
from backend.core.logging.context import get_log_context
from backend.core.logging.sanitizer import sanitize_fields, sanitize_message


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def category_enabled(category: str) -> bool:
    settings = load_logging_settings()
    return settings.enabled and settings.category_enabled(category)


def log_event(
    logger: logging.Logger,
    level: int,
    category: str,
    event: str,
    message: str,
    **fields: object,
) -> None:
    settings = load_logging_settings()
    if not settings.enabled or not settings.category_enabled(category):
        return

    sanitized_fields = sanitize_fields(fields)
    for key, value in get_log_context().items():
        sanitized_fields.setdefault(key, value)

    logger.log(
        level,
        sanitize_message(message),
        extra={
            "category": category,
            "event": event,
            "log_fields": sanitized_fields,
        },
    )
