from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.api.modules.decision_workflow.choice_group.application import (
    choice_service as choice_service_module,
)
from backend.api.modules.decision_workflow.choice_group.application.choice_service import (
    ChoiceService,
)


def _service():
    service = ChoiceService()
    service.patch_engine = SimpleNamespace(apply_patch=AsyncMock())
    service._reject_siblings = AsyncMock()
    return service


@pytest.mark.asyncio
async def test_accept_patch_choice_preserves_invalidation_and_slot_cleanup(monkeypatch):
    choice = SimpleNamespace(
        id=13,
        title="Apply model changes",
        status="candidate",
        patch={
            "addNodes": [
                {"kind": "actor"},
                {"kind": "feature"},
                {"kind": "scenario"},
                {"kind": "acceptance_criterion"},
            ],
            "updateNodes": [
                {"kind": "business_object"},
                {"kind": "flow"},
                {"kind": "flow_step"},
                {"kind": "scope"},
            ],
            "deleteNodes": [],
            "addLinks": [
                {"type": "feature_actor_relation"},
                {"relationType": "flow_feature"},
            ],
        },
    )
    group = SimpleNamespace(
        status="open",
        slot_id=17,
        source_type="generation",
        stage=None,
        issue_id=None,
        issue_code=None,
        context_hash="context-hash",
    )
    slot = SimpleNamespace(id=17)
    query_result = SimpleNamespace(scalar_one_or_none=lambda: slot)
    session = SimpleNamespace(
        execute=AsyncMock(return_value=query_result),
        delete=AsyncMock(),
        add=MagicMock(),
        flush=AsyncMock(),
    )
    notifier = SimpleNamespace(mark_stale=AsyncMock())
    monkeypatch.setattr(choice_service_module, "get_notifier", lambda: notifier)
    service = _service()

    result = await service._accept_patch_choice(choice, group, 5, session)

    assert result == {
        "resolved_issue_ids": [],
        "remaining_issue_ids": [],
        "new_issue_ids": [],
        "partially_resolved": False,
    }
    service.patch_engine.apply_patch.assert_awaited_once_with(
        5,
        choice.patch,
        session,
    )
    service._reject_siblings.assert_awaited_once_with(choice, group, session)
    assert choice.status == "accepted"
    assert group.status == "resolved"
    assert group.slot_id is None
    session.delete.assert_awaited_once_with(slot)
    notifier.mark_stale.assert_awaited_once_with(
        project_id=5,
        stages={"what", "how", "scope"},
        perception_kinds={
            "ACTOR",
            "FEATURE",
            "SCENARIO",
            "ACCEPTANCE_CRITERION",
            "FLOW",
            "SCOPE",
        },
        session=session,
    )
    session.flush.assert_awaited_once_with()
    audit = session.add.call_args.args[0]
    assert audit.action_type == "accept_choice"
    assert audit.payload == {
        "issue_code": None,
        "resolution_type": "choice",
        "choice_id": "13",
        "solver_name": "Apply model changes",
        "context_hash": "context-hash",
        "resolved_issue_ids": [],
        "new_issue_ids": [],
        "partially_resolved": False,
    }


@pytest.mark.asyncio
async def test_accept_issue_patch_choice_preserves_regression_diff(monkeypatch):
    choice = SimpleNamespace(
        id=21,
        title="Repair issue",
        status="candidate",
        patch={},
    )
    group = SimpleNamespace(
        status="open",
        slot_id=None,
        source_type="issue_repair",
        stage="what",
        issue_id="target-issue",
        issue_code="TARGET_CODE",
        context_hash="context-hash",
    )
    session = SimpleNamespace(
        execute=AsyncMock(),
        delete=AsyncMock(),
        add=MagicMock(),
        flush=AsyncMock(),
    )
    service = _service()

    detector = SimpleNamespace(
        detect=AsyncMock(
            side_effect=[
                [
                    SimpleNamespace(issueId="old", code="OTHER_CODE"),
                    SimpleNamespace(issueId="remaining", code="TARGET_CODE"),
                ],
                [
                    SimpleNamespace(issueId="remaining", code="TARGET_CODE"),
                    SimpleNamespace(issueId="new", code="OTHER_CODE"),
                ],
            ]
        )
    )
    import backend.core.detectors as detector_module
    import backend.core.issue_resolution.resolution_verifier as verifier_module

    monkeypatch.setattr(detector_module, "WhatIssueDetector", lambda: detector)
    monkeypatch.setattr(
        detector_module,
        "HowIssueDetector",
        lambda: SimpleNamespace(),
    )
    monkeypatch.setattr(
        detector_module,
        "ScopeIssueDetector",
        lambda: SimpleNamespace(),
    )
    verify = AsyncMock(return_value=(["old"], ["remaining"]))
    monkeypatch.setattr(verifier_module, "verify_issue_resolved", verify)

    result = await service._accept_patch_choice(choice, group, 5, session)

    assert result == {
        "resolved_issue_ids": ["old"],
        "remaining_issue_ids": ["remaining"],
        "new_issue_ids": ["new"],
        "partially_resolved": True,
    }
    verify.assert_awaited_once_with(
        project_id=5,
        issue_code="TARGET_CODE",
        issue_id="target-issue",
        stage="what",
        session=session,
    )
    assert detector.detect.await_count == 2
    audit = session.add.call_args.args[0]
    assert audit.payload["resolved_issue_ids"] == ["old"]
    assert audit.payload["new_issue_ids"] == ["new"]
    assert audit.payload["partially_resolved"] is True
