from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.modules.project_lifecycle.application.project_service import (
    ProjectService,
)


def _session_for(project):
    result = MagicMock()
    result.scalar_one_or_none.return_value = project
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_stage_transition_force_does_not_bypass_incomplete_content():
    project = SimpleNamespace(
        id=1,
        public_id="public-1",
        unlocked_stages="",
    )
    session = _session_for(project)
    service = ProjectService()
    service.get_stage_progress = AsyncMock(
        return_value={
            "stages": [
                {
                    "stage": "what",
                    "status_code": "in_progress",
                    "content_complete": False,
                }
            ]
        }
    )
    finding = SimpleNamespace(findingId="what:GATE:1")

    with patch(
        "backend.api.modules.diagnosis_quality.public."
        "FindingService.list_findings",
        new=AsyncMock(return_value=[finding]),
    ):
        result = await service.stage_transition(
            1,
            "enter_how",
            True,
            session,
            operator_id=7,
        )

    assert result == {
        "status": "blocked",
        "action": "enter_how",
        "unlocked_stage": None,
        "target_route": None,
        "unlocked_stages": [],
        "blocking_findings": [finding],
    }
    session.add.assert_not_called()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_stage_transition_force_preserves_unlock_and_audit_payload():
    project = SimpleNamespace(
        id=1,
        public_id="public-1",
        unlocked_stages="what",
    )
    session = _session_for(project)
    service = ProjectService()
    service.get_stage_progress = AsyncMock(
        return_value={
            "stages": [
                {
                    "stage": "how",
                    "status_code": "ready",
                    "content_complete": True,
                }
            ]
        }
    )
    finding = SimpleNamespace(findingId="how:GATE:2")

    with patch(
        "backend.api.modules.diagnosis_quality.public."
        "FindingService.list_findings",
        new=AsyncMock(return_value=[finding]),
    ):
        result = await service.stage_transition(
            1,
            "enter_scope",
            True,
            session,
            operator_id=7,
        )

    audit = session.add.call_args.args[0]
    assert project.unlocked_stages == "what,how"
    assert audit.action_type == "stage_transition_forced"
    assert audit.actor_user_id == 7
    assert audit.payload == {
        "action": "enter_scope",
        "unlock_stage": "how",
        "force": True,
        "is_forced_transition": True,
        "from_stage": "how",
        "target_stage": "scope",
        "blocking_finding_ids": ["how:GATE:2"],
        "operator_id": 7,
        "bypass_findings_count": 1,
    }
    assert result == {
        "status": "unlocked",
        "action": "enter_scope",
        "unlocked_stage": "how",
        "target_route": "/projects/public-1/scope",
        "unlocked_stages": ["what", "how"],
        "blocking_findings": [],
    }
    session.commit.assert_awaited_once()
