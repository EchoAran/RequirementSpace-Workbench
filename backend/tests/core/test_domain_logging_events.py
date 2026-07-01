import logging

from backend.core.logging import log_event
from backend.core.logging.events import (
    AI_ADD_DRAFT_CREATED,
    AI_ADD_DRAFT_DISCARDED,
    AI_ADD_LLM_PARSE_FAILED,
    AI_ADD_SESSION_CREATED,
    AI_EXPLAIN_COMPLETED,
    AI_EXPLAIN_FAILED,
    CHOICE_GROUP_CREATED,
    CHOICE_GROUP_CREATE_REQUESTED,
    CHOICE_GROUP_GENERATION_FAILED,
    CHOICE_GROUP_REGENERATED,
    CHOICE_GROUP_RESOLVED,
    FINDING_DETECTION_COMPLETED,
    FINDING_DETECTION_FAILED,
    FINDING_DETECTION_STARTED,
    ISSUE_REPAIR_DRAFT_CREATED,
    ISSUE_REPAIR_FAILED,
    PERCEPTION_JOB_COMPLETED,
    PERCEPTION_JOB_FAILED,
    PERCEPTION_JOB_STARTED,
    PERCEPTION_SLOT_FILLING_DRAFT_CREATED,
    PROJECT_INTERVIEW_COMPLETE_FAILED,
    PROJECT_INTERVIEW_MESSAGE_PROCESSED,
)


DOMAIN_EVENTS = [
    CHOICE_GROUP_CREATE_REQUESTED,
    CHOICE_GROUP_CREATED,
    CHOICE_GROUP_GENERATION_FAILED,
    CHOICE_GROUP_REGENERATED,
    CHOICE_GROUP_RESOLVED,
    AI_ADD_SESSION_CREATED,
    AI_ADD_DRAFT_CREATED,
    AI_ADD_DRAFT_DISCARDED,
    AI_ADD_LLM_PARSE_FAILED,
    AI_EXPLAIN_COMPLETED,
    AI_EXPLAIN_FAILED,
    PROJECT_INTERVIEW_MESSAGE_PROCESSED,
    PROJECT_INTERVIEW_COMPLETE_FAILED,
    FINDING_DETECTION_STARTED,
    FINDING_DETECTION_COMPLETED,
    FINDING_DETECTION_FAILED,
    ISSUE_REPAIR_DRAFT_CREATED,
    ISSUE_REPAIR_FAILED,
    PERCEPTION_JOB_STARTED,
    PERCEPTION_JOB_COMPLETED,
    PERCEPTION_JOB_FAILED,
    PERCEPTION_SLOT_FILLING_DRAFT_CREATED,
]


def _events(caplog):
    return [record for record in caplog.records if hasattr(record, "event")]


def test_domain_events_are_suppressed_when_domain_category_disabled(monkeypatch, caplog):
    monkeypatch.setenv("LOG_ENABLED", "true")
    monkeypatch.setenv("LOG_ENABLED_CATEGORIES", "request,db,llm,ai_operation,auth,audit")

    logger = logging.getLogger("backend.tests.domain_logging.disabled")

    with caplog.at_level(logging.INFO):
        log_event(
            logger,
            logging.INFO,
            "domain",
            CHOICE_GROUP_CREATED,
            "Choice group created",
            project_id=1,
        )

    assert not _events(caplog)


def test_domain_events_emit_summary_fields_without_sensitive_content(monkeypatch, caplog):
    monkeypatch.setenv("LOG_ENABLED", "true")
    monkeypatch.setenv("LOG_ENABLED_CATEGORIES", "domain")

    logger = logging.getLogger("backend.tests.domain_logging.enabled")

    with caplog.at_level(logging.INFO):
        for event in DOMAIN_EVENTS:
            log_event(
                logger,
                logging.INFO,
                "domain",
                event,
                "Domain event",
                project_id=1,
                user_id=2,
                api_key="sk-test-secret-value",
                password="plain-password",
                prompt="raw prompt should be redacted",
            )

    events = _events(caplog)
    assert {record.event for record in events} == set(DOMAIN_EVENTS)
    for record in events:
        assert record.category == "domain"
        assert record.log_fields["project_id"] == 1
        assert record.log_fields["user_id"] == 2
        assert record.log_fields["api_key"] == "********"
        assert record.log_fields["password"] == "********"
        assert record.log_fields["prompt"] == "********"
