from __future__ import annotations

import logging

from backend.core.logging.context import LOG_CONTEXT_FIELDS, get_log_context


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        context = get_log_context()
        for field in LOG_CONTEXT_FIELDS:
            if not hasattr(record, field):
                setattr(record, field, context.get(field))
        return True
