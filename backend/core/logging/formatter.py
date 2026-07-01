from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from backend.core.logging.context import LOG_CONTEXT_FIELDS


def _timestamp(record: logging.LogRecord) -> str:
    return datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()


def _record_fields(record: logging.LogRecord) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    event = getattr(record, "event", None)
    category = getattr(record, "category", None)
    if event:
        fields["event"] = event
    if category:
        fields["category"] = category

    for field in LOG_CONTEXT_FIELDS:
        value = getattr(record, field, None)
        if value is not None:
            fields[field] = value

    log_fields = getattr(record, "log_fields", None)
    if isinstance(log_fields, dict):
        fields.update({key: value for key, value in log_fields.items() if value is not None})
    return fields


class TextLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        fields = _record_fields(record)
        rendered_fields = " ".join(
            f"{key}={json.dumps(value, ensure_ascii=False)}"
            for key, value in fields.items()
        )
        message = json.dumps(record.getMessage(), ensure_ascii=False)
        prefix = f"{self.formatTime(record, self.datefmt)} {record.levelname} {record.name}"
        if rendered_fields:
            return f"{prefix} {rendered_fields} message={message}"
        return f"{prefix} message={message}"


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": _timestamp(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(_record_fields(record))
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)
