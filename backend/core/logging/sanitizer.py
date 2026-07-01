from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from backend.core.security import sanitize_message as _sanitize_security_message


SENSITIVE_FIELD_NAMES = {
    "api_key",
    "llm_api_key",
    "encrypted_api_key",
    "llm_config_encryption_key",
    "authorization",
    "cookie",
    "set-cookie",
    "password",
    "token",
    "secret",
    "session",
    "prompt",
    "query",
    "content",
    "response",
    "payload",
    "draft_payload",
    "response_payload",
}


def sanitize_message(value: object) -> str:
    return _sanitize_security_message(str(value) if value is not None else "")


def sanitize_database_url(value: str) -> str:
    if not value:
        return ""

    try:
        parts = urlsplit(value)
    except Exception:
        return "[sanitized database url]"

    if not parts.netloc or "@" not in parts.netloc:
        return sanitize_message(value)

    userinfo, hostinfo = parts.netloc.rsplit("@", 1)
    if ":" in userinfo:
        username = userinfo.split(":", 1)[0]
        userinfo = f"{username}:****"
    sanitized = urlunsplit(
        (parts.scheme, f"{userinfo}@{hostinfo}", parts.path, parts.query, parts.fragment)
    )
    return sanitize_message(sanitized)


def sanitize_mapping(value: Mapping[str, object]) -> dict[str, object]:
    sanitized: dict[str, object] = {}
    for key, item in value.items():
        normalized_key = str(key).strip().lower()
        if normalized_key in SENSITIVE_FIELD_NAMES:
            sanitized[key] = "********"
        elif isinstance(item, Mapping):
            sanitized[key] = sanitize_mapping(item)
        elif isinstance(item, str):
            sanitized[key] = sanitize_message(item)
        else:
            sanitized[key] = item
    return sanitized


def preview_text(value: str, max_chars: int = 200) -> str:
    sanitized = sanitize_message(value)
    if max_chars < 0:
        max_chars = 0
    if len(sanitized) <= max_chars:
        return sanitized
    return sanitized[:max_chars]


def sanitize_fields(fields: Mapping[str, Any]) -> dict[str, object]:
    return sanitize_mapping(fields)
