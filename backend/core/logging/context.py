from __future__ import annotations

from contextvars import ContextVar
from typing import Any


LOG_CONTEXT_FIELDS = ("request_id", "user_id", "project_id", "operation")

_log_context: ContextVar[dict[str, object]] = ContextVar("log_context", default={})


def set_log_context(**fields: object) -> None:
    current = dict(_log_context.get())
    for key, value in fields.items():
        if key in LOG_CONTEXT_FIELDS and value is not None:
            current[key] = value
    _log_context.set(current)


def clear_log_context() -> None:
    _log_context.set({})


def get_log_context() -> dict[str, object]:
    return dict(_log_context.get())


def context_value(key: str, default: Any = None) -> Any:
    return _log_context.get().get(key, default)
