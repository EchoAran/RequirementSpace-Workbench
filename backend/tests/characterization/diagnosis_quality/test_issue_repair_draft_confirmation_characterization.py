from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.api.modules.diagnosis_quality.issue_repair.application import (
    issue_repair_draft_service as draft_service_module,
)
from backend.api.modules.diagnosis_quality.issue_repair.application.issue_repair_draft_service import (
    IssueRepairDraftService,
)


def _draft(**overrides):
    values = {
        "project_id": 7,
        "workspace_id": 2,
        "status": "pending",
        "target": {"target_type": "flow", "target_id": 11},
        "context_hash": "same-hash",
        "patch": {"updateNodes": [{"id": 11}]},
        "issue_code": "HOW_ISSUE",
        "stage": "how",
        "title": "Repair flow",
        "issue_id": "issue-1",
        "repair_type": "ai",
        "validation_report": {},
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _service(draft):
    service = IssueRepairDraftService()
    service._load_draft = AsyncMock(return_value=draft)
    service.validator = SimpleNamespace(validate=AsyncMock())
    service.patch_engine = SimpleNamespace(apply_patch=AsyncMock())
    return service


@pytest.mark.asyncio
async def test_confirm_draft_marks_changed_context_stale(monkeypatch):
    draft = _draft()
    service = _service(draft)
    session = SimpleNamespace(flush=AsyncMock(), add=MagicMock())
    monkeypatch.setattr(
        draft_service_module,
        "load_target_entity_snapshot",
        AsyncMock(return_value={"id": 11}),
    )
    monkeypatch.setattr(
        draft_service_module,
        "_compute_context_hash_from_target",
        MagicMock(return_value="changed-hash"),
    )

    result = await service.confirm_draft(7, "draft-1", session, workspace_id=2)

    assert result == {
        "message": "issue_repair_draft_stale",
        "draft_id": "draft-1",
        "status": "stale",
        "recommended_action": "regenerate",
        "resolved_issue_ids": [],
        "remaining_issue_ids": [],
    }
    assert draft.status == "stale"
    session.flush.assert_awaited_once_with()
    service.validator.validate.assert_not_awaited()
    service.patch_engine.apply_patch.assert_not_awaited()
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_confirm_draft_marks_rejected_patch_invalid(monkeypatch):
    draft = _draft()
    service = _service(draft)
    service.validator.validate.return_value = {
        "valid": False,
        "errors": ["missing target"],
    }
    session = SimpleNamespace(flush=AsyncMock(), add=MagicMock())
    monkeypatch.setattr(
        draft_service_module,
        "load_target_entity_snapshot",
        AsyncMock(return_value={"id": 11}),
    )
    monkeypatch.setattr(
        draft_service_module,
        "_compute_context_hash_from_target",
        MagicMock(return_value="same-hash"),
    )

    result = await service.confirm_draft(7, "draft-1", session, workspace_id=2)

    assert result == {
        "message": "issue_repair_draft_invalid",
        "draft_id": "draft-1",
        "status": "invalid",
        "resolved_issue_ids": [],
        "remaining_issue_ids": [],
    }
    assert draft.status == "invalid"
    assert draft.validation_report == {
        "valid": False,
        "errors": ["missing target"],
    }
    service.validator.validate.assert_awaited_once_with(
        project_id=7,
        issue_code="HOW_ISSUE",
        patch=draft.patch,
        session=session,
    )
    session.flush.assert_awaited_once_with()
    service.patch_engine.apply_patch.assert_not_awaited()
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_confirm_draft_preserves_apply_diff_and_audit_behavior(monkeypatch):
    draft = _draft()
    service = _service(draft)
    service.validator.validate.return_value = {"valid": True}
    session = SimpleNamespace(flush=AsyncMock(), add=MagicMock())
    monkeypatch.setattr(
        draft_service_module,
        "load_target_entity_snapshot",
        AsyncMock(return_value={"id": 11}),
    )
    monkeypatch.setattr(
        draft_service_module,
        "_compute_context_hash_from_target",
        MagicMock(return_value="same-hash"),
    )
    stale_marker = AsyncMock()
    monkeypatch.setattr(
        draft_service_module,
        "mark_perception_jobs_stale",
        stale_marker,
    )

    detector = SimpleNamespace(
        detect=AsyncMock(
            side_effect=[
                [
                    SimpleNamespace(issueId="resolved", code="HOW_ISSUE"),
                    SimpleNamespace(issueId="remaining", code="HOW_ISSUE"),
                ],
                [
                    SimpleNamespace(issueId="remaining", code="HOW_ISSUE"),
                    SimpleNamespace(issueId="new", code="OTHER_ISSUE"),
                ],
            ]
        )
    )
    import backend.core.detectors as detector_module

    monkeypatch.setattr(detector_module, "HowIssueDetector", lambda: detector)
    monkeypatch.setattr(
        detector_module,
        "WhatIssueDetector",
        lambda: SimpleNamespace(),
    )
    monkeypatch.setattr(
        detector_module,
        "ScopeIssueDetector",
        lambda: SimpleNamespace(),
    )

    result = await service.confirm_draft(7, "draft-1", session, workspace_id=2)

    assert result == {
        "message": "issue_repair_draft_applied",
        "draft_id": "draft-1",
        "status": "applied",
        "resolved_issue_ids": ["resolved"],
        "remaining_issue_ids": ["remaining"],
        "new_issue_ids": ["new"],
        "partially_resolved": True,
    }
    assert draft.status == "applied"
    assert draft.validation_report == {"valid": True}
    service.patch_engine.apply_patch.assert_awaited_once_with(
        7,
        draft.patch,
        session,
        workspace_id=2,
    )
    stale_marker.assert_awaited_once_with(
        project_id=7,
        stages={"how"},
        perception_kinds={"FLOW"},
        session=session,
        workspace_id=2,
    )
    assert detector.detect.await_count == 2
    assert session.flush.await_count == 2
    audit = session.add.call_args.args[0]
    assert audit.action_type == "issue_repair_confirmed"
    assert audit.payload == {
        "issue_code": "HOW_ISSUE",
        "resolution_type": "repair_draft",
        "draft_id": "draft-1",
        "solver_name": "ai",
        "context_hash": "same-hash",
        "validation_report": {"valid": True},
        "resolved_issue_ids": ["resolved"],
        "new_issue_ids": ["new"],
        "partially_resolved": True,
    }
