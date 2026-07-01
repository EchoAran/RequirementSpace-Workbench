from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, Mapping


DEFAULT_LOG_CATEGORIES = frozenset(
    {"request", "db", "llm", "ai_operation", "auth", "audit"}
)
SUPPORTED_LOG_CATEGORIES = frozenset(
    {
        "request",
        "db",
        "llm",
        "llm_content",
        "ai_operation",
        "auth",
        "audit",
        "domain",
        "sql",
    }
)
SUPPORTED_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
SUPPORTED_LOG_FORMATS = frozenset({"text", "json"})


@dataclass(frozen=True)
class LoggingSettings:
    enabled: bool
    level: str
    format: Literal["text", "json"]
    enabled_categories: frozenset[str]

    def category_enabled(self, category: str) -> bool:
        return category.strip().lower() in self.enabled_categories


def _parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "y", "on"}:
        return True
    if normalized in {"false", "0", "no", "n", "off"}:
        return False
    return default


def _parse_level(value: str | None) -> str:
    normalized = (value or "INFO").strip().upper()
    if normalized in SUPPORTED_LOG_LEVELS:
        return normalized
    return "INFO"


def _parse_format(value: str | None) -> Literal["text", "json"]:
    normalized = (value or "text").strip().lower()
    if normalized in SUPPORTED_LOG_FORMATS:
        return normalized  # type: ignore[return-value]
    return "text"


def _parse_categories(value: str | None) -> frozenset[str]:
    if value is None:
        return DEFAULT_LOG_CATEGORIES

    categories = {
        item.strip().lower()
        for item in value.split(",")
        if item.strip()
    }
    return frozenset(
        category for category in categories if category in SUPPORTED_LOG_CATEGORIES
    )


def load_logging_settings(
    environ: Mapping[str, str] | None = None,
) -> LoggingSettings:
    source = environ if environ is not None else os.environ
    return LoggingSettings(
        enabled=_parse_bool(source.get("LOG_ENABLED"), default=True),
        level=_parse_level(source.get("LOG_LEVEL")),
        format=_parse_format(source.get("LOG_FORMAT")),
        enabled_categories=_parse_categories(source.get("LOG_ENABLED_CATEGORIES")),
    )
