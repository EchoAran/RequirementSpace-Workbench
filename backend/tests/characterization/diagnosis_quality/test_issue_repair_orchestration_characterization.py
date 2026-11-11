from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.api.modules.diagnosis_quality.issue_repair.application.issue_repair_service import (
    IssueRepairService,
)
from backend.core.issue_resolution.ai.base_ai_solver import (
    RepairProposal,
    RepairResult,
)
from backend.schemas import IssueTarget


@pytest.mark.asyncio
async def test_ai_registry_fallback_preserves_metadata_and_response_context():
    service = IssueRepairService()
    ai_solver = SimpleNamespace(
        solve=AsyncMock(return_value=RepairResult(fallback_to_registry=True))
    )
    resolution = SimpleNamespace(
        resolutionType="open_panel",
        to_dict=lambda: {
            "resolution_type": "open_panel",
            "action": {"kind": "open_panel"},
        },
    )
    service._solver_registry = SimpleNamespace(
        resolve=AsyncMock(return_value=resolution)
    )
    service._draft_factory = SimpleNamespace(create_draft=AsyncMock())
    session = SimpleNamespace()
    target = {"target_type": "feature", "target_id": 3}
    issue_target = IssueTarget(targetType="feature", targetId=3)
    metadata = {"source": "characterization"}

    result = await service._resolve_with_ai(
        project_id=5,
        issue_code="TEST_ISSUE",
        issue_id="issue-1",
        target=target,
        issue_target=issue_target,
        stage="what",
        matched_issue=SimpleNamespace(),
        issue_fp="fingerprint",
        context_hash="context-hash",
        workspace_id=2,
        ai_solver=ai_solver,
        metadata=metadata,
        session=session,
    )

    service._solver_registry.resolve.assert_awaited_once_with(
        project_id=5,
        issue_code="TEST_ISSUE",
        target=issue_target,
        metadata=metadata,
        session=session,
    )
    service._draft_factory.create_draft.assert_not_awaited()
    assert result == {
        "resolution_type": "open_panel",
        "action": {"kind": "open_panel"},
        "project_id": 5,
        "issue_fingerprint": "fingerprint",
        "context_hash": "context-hash",
    }


@pytest.mark.asyncio
async def test_ai_invalid_single_candidate_returns_manual_action():
    service = IssueRepairService()
    candidate = RepairProposal(
        repair_type="update_feature",
        title="Update feature",
        rationale="Align the model",
        patch={"updateNodes": [{"kind": "feature", "id": 3}]},
    )
    ai_solver = SimpleNamespace(
        solve=AsyncMock(return_value=RepairResult(candidates=[candidate]))
    )
    service._validator = SimpleNamespace(
        validate=AsyncMock(
            return_value={
                "valid": False,
                "errors": ["target missing", "invalid update"],
            }
        )
    )
    session = SimpleNamespace()
    target = {"target_type": "feature", "target_id": 3}

    result = await service._resolve_with_ai(
        project_id=5,
        issue_code="TEST_ISSUE",
        issue_id="issue-1",
        target=target,
        issue_target=IssueTarget(targetType="feature", targetId=3),
        stage="what",
        matched_issue=SimpleNamespace(),
        issue_fp="fingerprint",
        context_hash="context-hash",
        workspace_id=2,
        ai_solver=ai_solver,
        metadata={},
        session=session,
    )

    service._validator.validate.assert_awaited_once_with(
        project_id=5,
        issue_code="TEST_ISSUE",
        patch=candidate.patch,
        session=session,
    )
    assert result["resolution_type"] == "manual_action"
    assert result["description"] == "target missing; invalid update"
    assert result["action"] == {
        "kind": "open_panel",
        "payload": {"target": target},
    }
    assert result["patch"] is None
    assert result["issue_fingerprint"] == "fingerprint"
    assert result["context_hash"] == "context-hash"
