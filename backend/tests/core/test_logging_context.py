import io
import logging

from backend.core.logging.context import clear_log_context, get_log_context, set_log_context
from backend.core.logging.filters import ContextFilter
from backend.core.logging.formatter import TextLogFormatter
from backend.core.logging.logger import log_event


def test_log_context_set_get_and_clear():
    clear_log_context()

    set_log_context(request_id="req-1", user_id=7, ignored="value")

    assert get_log_context() == {"request_id": "req-1", "user_id": 7}

    clear_log_context()

    assert get_log_context() == {}


def test_log_event_includes_context_fields(monkeypatch):
    clear_log_context()
    set_log_context(request_id="req-ctx", project_id=42)

    logger = logging.getLogger("backend.tests.logging_context")
    logger.handlers = []
    logger.propagate = False
    logger.setLevel(logging.INFO)
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(ContextFilter())
    handler.setFormatter(TextLogFormatter())
    logger.addHandler(handler)

    monkeypatch.setenv("LOG_ENABLED", "true")
    monkeypatch.setenv("LOG_ENABLED_CATEGORIES", "request")
    log_event(
        logger,
        logging.INFO,
        "request",
        "http_request_completed",
        "request completed",
        status_code=200,
    )

    output = stream.getvalue()
    assert "event=\"http_request_completed\"" in output
    assert "request_id=\"req-ctx\"" in output
    assert "project_id=42" in output
    assert "status_code=200" in output

    clear_log_context()
