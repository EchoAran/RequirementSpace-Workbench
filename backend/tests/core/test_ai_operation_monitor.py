import logging

import pytest

from backend.core.ai_operation_monitor import (
    log_ai_operation_result,
    monitor_ai_operation,
)


def _events(caplog):
    return [record for record in caplog.records if hasattr(record, "event")]


def test_monitor_ai_operation_logs_completed_event(monkeypatch, caplog):
    monkeypatch.setenv("LOG_ENABLED", "true")
    monkeypatch.setenv("LOG_ENABLED_CATEGORIES", "ai_operation")

    with caplog.at_level(logging.INFO):
        with monitor_ai_operation(
            "generation_choice_group",
            project_id=12,
            generation_type="feature",
            issue_code="missing_actor",
            attempt=2,
        ):
            pass

    completed = [record for record in _events(caplog) if record.event == "ai_operation_completed"]
    assert len(completed) == 1
    fields = completed[0].log_fields
    assert fields["operation"] == "generation_choice_group"
    assert fields["project_id"] == 12
    assert fields["generation_type"] == "feature"
    assert fields["issue_code"] == "missing_actor"
    assert fields["attempt"] == 2
    assert isinstance(fields["duration_ms"], int)


def test_monitor_ai_operation_logs_failed_event_and_reraises(monkeypatch, caplog):
    monkeypatch.setenv("LOG_ENABLED", "true")
    monkeypatch.setenv("LOG_ENABLED_CATEGORIES", "ai_operation")

    with pytest.raises(ValueError):
        with caplog.at_level(logging.INFO):
            with monitor_ai_operation("llm_api_call", project_id=7):
                raise ValueError("boom")

    failed = [record for record in _events(caplog) if record.event == "ai_operation_failed"]
    assert len(failed) == 1
    fields = failed[0].log_fields
    assert fields["operation"] == "llm_api_call"
    assert fields["project_id"] == 7
    assert fields["error_type"] == "ValueError"


def test_log_ai_operation_result_logs_aggregate_fields(monkeypatch, caplog):
    monkeypatch.setenv("LOG_ENABLED", "true")
    monkeypatch.setenv("LOG_ENABLED_CATEGORIES", "ai_operation")

    with caplog.at_level(logging.INFO):
        log_ai_operation_result(
            "generation_choice_group",
            project_id=3,
            generation_type="scenario",
            issue_code="weak_goal",
            duration_ms=123,
            success_count=2,
            failure_count=1,
            status="open",
        )

    result = [record for record in _events(caplog) if record.event == "ai_operation_result"]
    assert len(result) == 1
    fields = result[0].log_fields
    assert fields["operation"] == "generation_choice_group"
    assert fields["project_id"] == 3
    assert fields["generation_type"] == "scenario"
    assert fields["issue_code"] == "weak_goal"
    assert fields["duration_ms"] == 123
    assert fields["success_count"] == 2
    assert fields["failure_count"] == 1
    assert fields["status"] == "open"


def test_ai_operation_category_disabled_suppresses_events(monkeypatch, caplog):
    monkeypatch.setenv("LOG_ENABLED", "true")
    monkeypatch.setenv("LOG_ENABLED_CATEGORIES", "llm")

    with caplog.at_level(logging.INFO):
        log_ai_operation_result("generation_choice_group", project_id=3)

    assert not _events(caplog)
