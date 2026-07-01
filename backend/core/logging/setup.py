from __future__ import annotations

import logging

from backend.core.logging.config import load_logging_settings
from backend.core.logging.filters import ContextFilter
from backend.core.logging.formatter import JsonLogFormatter, TextLogFormatter


_HANDLER_MARKER = "_requirementspace_logging_handler"


def _build_formatter(format_name: str) -> logging.Formatter:
    if format_name == "json":
        return JsonLogFormatter()
    return TextLogFormatter(datefmt="%Y-%m-%d %H:%M:%S")


def configure_logging() -> None:
    settings = load_logging_settings()
    level = getattr(logging, settings.level, logging.INFO)
    formatter = _build_formatter(settings.format)
    context_filter = ContextFilter()

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    target_handler = None
    for handler in root_logger.handlers:
        if getattr(handler, _HANDLER_MARKER, False):
            target_handler = handler
            break

    if target_handler is None:
        if root_logger.handlers:
            target_handler = root_logger.handlers[0]
        else:
            target_handler = logging.StreamHandler()
            root_logger.addHandler(target_handler)
        setattr(target_handler, _HANDLER_MARKER, True)

    target_handler.setLevel(level)
    target_handler.setFormatter(formatter)
    if not any(isinstance(item, ContextFilter) for item in target_handler.filters):
        target_handler.addFilter(context_filter)

    logging.getLogger("backend").setLevel(level)
    logging.getLogger("uvicorn").setLevel(level)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(
        logging.INFO if settings.category_enabled("sql") else logging.WARNING
    )
