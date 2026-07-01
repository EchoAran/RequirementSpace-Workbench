import io
import json
import logging

from backend.core.logging.config import load_logging_settings
from backend.core.logging.filters import ContextFilter
from backend.core.logging.formatter import JsonLogFormatter, TextLogFormatter
from backend.core.logging.logger import category_enabled, log_event
from backend.core.logging.context import clear_log_context, set_log_context
from backend.core.logging.setup import configure_logging


def test_logging_settings_defaults_to_safe_core_categories():
    settings = load_logging_settings({})

    assert settings.enabled is True
    assert settings.level == "INFO"
    assert settings.format == "text"
    assert settings.enabled_categories == frozenset(
        {"request", "db", "llm", "ai_operation", "auth", "audit"}
    )


def test_logging_settings_parses_values_and_ignores_unknown_categories():
    settings = load_logging_settings(
        {
            "LOG_ENABLED": "no",
            "LOG_LEVEL": "debug",
            "LOG_FORMAT": "json",
            "LOG_ENABLED_CATEGORIES": " request, LLM_Content,unknown,, SQL ",
        }
    )

    assert settings.enabled is False
    assert settings.level == "DEBUG"
    assert settings.format == "json"
    assert settings.enabled_categories == frozenset({"request", "llm_content", "sql"})


def test_logging_settings_falls_back_for_invalid_level_and_format():
    settings = load_logging_settings(
        {
            "LOG_LEVEL": "verbose",
            "LOG_FORMAT": "xml",
        }
    )

    assert settings.level == "INFO"
    assert settings.format == "text"


def test_category_enabled_reads_current_environment(monkeypatch):
    monkeypatch.setenv("LOG_ENABLED", "true")
    monkeypatch.setenv("LOG_ENABLED_CATEGORIES", "llm,llm_content")

    assert category_enabled("llm") is True
    assert category_enabled("db") is False


def test_log_event_obeys_enabled_and_category(monkeypatch):
    logger = logging.getLogger("backend.tests.logging_config")
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
    log_event(logger, logging.INFO, "llm", "llm_api_call_completed", "hidden")
    assert stream.getvalue() == ""

    log_event(logger, logging.INFO, "request", "http_request_completed", "visible")
    assert "event=\"http_request_completed\"" in stream.getvalue()
    assert "visible" in stream.getvalue()


def test_json_formatter_outputs_stable_json_fields():
    logger = logging.getLogger("backend.tests.logging_json")
    record = logger.makeRecord(
        logger.name,
        logging.INFO,
        __file__,
        10,
        "hello",
        args=(),
        exc_info=None,
        extra={
            "event": "sample_event",
            "category": "request",
            "request_id": "req-1",
            "log_fields": {"duration_ms": 12},
        },
    )

    payload = json.loads(JsonLogFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "backend.tests.logging_json"
    assert payload["message"] == "hello"
    assert payload["event"] == "sample_event"
    assert payload["category"] == "request"
    assert payload["request_id"] == "req-1"
    assert payload["duration_ms"] == 12


def test_configure_logging_applies_json_formatter_to_existing_root_handler(monkeypatch):
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    original_level = root_logger.level

    stream = io.StringIO()
    existing_handler = logging.StreamHandler(stream)
    existing_handler.setFormatter(logging.Formatter("%(levelname)s:%(message)s"))

    root_logger.handlers = [existing_handler]
    root_logger.setLevel(logging.WARNING)
    clear_log_context()
    set_log_context(request_id="req-existing-handler")

    monkeypatch.setenv("LOG_ENABLED", "true")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("LOG_FORMAT", "json")
    monkeypatch.setenv("LOG_ENABLED_CATEGORIES", "request")

    try:
        configure_logging()
        logging.getLogger("backend.tests.configure").info("hello")
    finally:
        root_logger.handlers = original_handlers
        root_logger.setLevel(original_level)
        clear_log_context()

    payload = json.loads(stream.getvalue())
    assert payload["level"] == "INFO"
    assert payload["logger"] == "backend.tests.configure"
    assert payload["message"] == "hello"
    assert payload["request_id"] == "req-existing-handler"
