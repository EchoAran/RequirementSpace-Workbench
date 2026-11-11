from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.modules.decision_workflow.ports.ports import (
    CandidateContext,
    GenerationCandidate,
)
from backend.api.modules.requirements_core.flow_refinement.application.choice_adapter import (
    FlowRefinementChoiceAdapter,
)


def _make_sample_payload(context_hash: str = "hash_valid_123") -> dict:
    return {
        "project_id": 1,
        "workspace_id": 2,
        "target_flow_id": 42,
        "target_flow_logical_uuid": "flow-uuid-42",
        "target_kind": "flow",
        "target_id": 42,
        "expected_workspace_version": context_hash,
        "context_hash": context_hash,
        "rationale": "Refined checkout with validation step",
        "steps_added": [
            {
                "temp_id": "temp_step_1",
                "name": "Validate Payment",
                "description": "Check card funds",
                "step_type": "systemAction",
                "position": 2,
            }
        ],
        "transitions_added": [
            {
                "temp_id": "temp_trans_1",
                "source_step_ref": 1,
                "target_step_ref": "temp_step_1",
                "condition_text": "cart_valid",
                "label": "Proceed",
                "is_default": True,
            }
        ],
        "transitions_updated": [],
        "rules_added": [
            {
                "temp_id": "temp_rule_1",
                "statement": "Payment Timeout after 30s",
                "name": "Payment Timeout",
                "description": "Timeout after 30s",
            }
        ],
        "rule_links_added": [],
        "business_objects_added": [],
        "step_object_links_added": [],
    }


@pytest.mark.asyncio
async def test_apply_choice_missing_hash_rejected():
    adapter = FlowRefinementChoiceAdapter()
    payload = _make_sample_payload()
    del payload["context_hash"]
    del payload["expected_workspace_version"]

    mock_session = AsyncMock()
    with pytest.raises(ValueError) as excinfo:
        await adapter.apply_candidate(payload, mock_session, workspace_id=2)
    assert "workspace_version_conflict" in str(excinfo.value)
    assert "missing candidate workspace version" in str(excinfo.value)


@pytest.mark.asyncio
async def test_apply_choice_stale_hash_rejected():
    adapter = FlowRefinementChoiceAdapter()
    payload = _make_sample_payload(context_hash="stale_server_hash")

    mock_session = AsyncMock()

    with patch(
        "backend.api.modules.requirements_core.flow_refinement.application.flow_refinement_service.load_flow_refinement_context"
    ) as mock_load_ctx:
        mock_ctx = MagicMock()
        mock_ctx.context_hash = "current_server_hash"
        mock_load_ctx.return_value = mock_ctx

        with pytest.raises(ValueError) as excinfo:
            await adapter.apply_candidate(payload, mock_session, workspace_id=2)
        assert "workspace_version_conflict" in str(excinfo.value)


@pytest.mark.asyncio
async def test_apply_choice_client_override_hash_ignored():
    adapter = FlowRefinementChoiceAdapter()
    payload = _make_sample_payload(context_hash="stale_server_hash")

    mock_session = AsyncMock()

    with patch(
        "backend.api.modules.requirements_core.flow_refinement.application.flow_refinement_service.load_flow_refinement_context"
    ) as mock_load_ctx:
        mock_ctx = MagicMock()
        mock_ctx.context_hash = "current_server_hash"
        mock_load_ctx.return_value = mock_ctx

        with pytest.raises(ValueError) as excinfo:
            await adapter.apply_candidate(
                payload,
                mock_session,
                expected_workspace_version="current_server_hash",
                      workspace_id=2,
            )
        # Client override does not bypass payload's stale hash!
        assert "workspace_version_conflict" in str(excinfo.value)
        assert "does not match candidate saved baseline" in str(excinfo.value)


@pytest.mark.asyncio
async def test_apply_choice_delegates_to_service():
    adapter = FlowRefinementChoiceAdapter()
    payload = _make_sample_payload(context_hash="valid_hash_456")

    mock_session = AsyncMock()
    mock_service = AsyncMock()
    mock_service.apply_refinement.return_value = {"status": "applied", "flow_id": 42}
    adapter._service = mock_service

    result = await adapter.apply_candidate(payload, mock_session, workspace_id=9)
    assert result["status"] == "applied"
    mock_service.apply_refinement.assert_awaited_once_with(
        payload=payload,
        session=mock_session,
        workspace_id=9,
        expected_workspace_version=None,
    )


@pytest.mark.asyncio
async def test_is_context_stale():
    adapter = FlowRefinementChoiceAdapter()
    payload = _make_sample_payload(context_hash="hash_100")
    choice = MagicMock()
    choice.payload = payload
    choice.project_id = 1

    mock_session = AsyncMock()

    with patch(
        "backend.api.modules.requirements_core.flow_refinement.application.choice_adapter.load_flow_refinement_context"
    ) as mock_load_ctx:
        # Same hash => not stale
        mock_ctx = MagicMock()
        mock_ctx.context_hash = "hash_100"
        mock_load_ctx.return_value = mock_ctx
        assert await adapter.is_context_stale(choice, mock_session) == (False, None)

        # Changed hash => stale
        mock_ctx.context_hash = "hash_200"
        assert await adapter.is_context_stale(choice, mock_session) == (True, "flow_refinement_context_changed")


def test_is_duplicate():
    adapter = FlowRefinementChoiceAdapter()
    c1 = GenerationCandidate(
        title="Candidate 1",
        rationale="desc",
        payload={
            "steps_added": [{"name": "Step A"}, {"name": "Step B"}],
            "transitions_added": [{"label": "trans 1"}],
        },
    )
    c2 = GenerationCandidate(
        title="Candidate 2",
        rationale="desc 2",
        payload={
            "steps_added": [{"name": "Step B"}, {"name": "Step A"}],
            "transitions_added": [{"label": "trans 1"}],
        },
    )
    c3 = GenerationCandidate(
        title="Candidate 3",
        rationale="desc 3",
        payload={
            "steps_added": [{"name": "Step C"}],
            "transitions_added": [],
        },
    )

    assert adapter.is_duplicate(c1, [c2]) is True
    assert adapter.is_duplicate(c3, [c1, c2]) is False


@pytest.mark.asyncio
async def test_generate_candidates_target_resolution():
    adapter = FlowRefinementChoiceAdapter()
    mock_service = AsyncMock()
    mock_service._generate_preview.return_value = (
        {
            "workspace_id": 2,
            "project_id": 1,
            "target_flow_id": 42,
            "target_flow_logical_uuid": "flow-42",
            "target_kind": "flow_step",
            "target_id": 5,
            "expected_workspace_version": "hash-1",
            "context_hash": "hash-1",
            "steps_added": [],
            "transitions_added": [],
            "transitions_updated": [],
            "rules_added": [],
            "rule_links_added": [],
            "business_objects_added": [],
            "step_object_links_added": [],
        },
        {
            "steps_added_count": 0,
            "transitions_added_count": 0,
            "rules_added_count": 0,
        },
    )
    adapter._service = mock_service

    mock_session = AsyncMock()

    # 1. Target with {flow_id, focus_step_id}
    await adapter.generate_candidate(
        CandidateContext(
            index=0,
            strategy="default",
            session=mock_session,
            project_id=1,
            target={"flow_id": 42, "focus_step_id": 5},
            workspace_id=2,
        )
    )
    call_kwargs_1 = mock_service._generate_preview.call_args.kwargs
    assert call_kwargs_1["target_kind"] == "flow_step"
    assert call_kwargs_1["target_id"] == 5
    assert call_kwargs_1["project_id"] == 1

    # 2. Target with {flow_id} only
    await adapter.generate_candidate(
        CandidateContext(
            index=0,
            strategy="default",
            session=mock_session,
            project_id=1,
            target={"flow_id": 42},
            workspace_id=2,
        )
    )
    call_kwargs_2 = mock_service._generate_preview.call_args.kwargs
    assert call_kwargs_2["target_kind"] == "flow"
    assert call_kwargs_2["target_id"] == 42
    assert call_kwargs_2["project_id"] == 1

    # 3. Missing target
    with pytest.raises(ValueError) as excinfo:
        await adapter.generate_candidate(
            CandidateContext(
                index=0,
                strategy="default",
                session=mock_session,
                project_id=1,
                target={},
                workspace_id=2,
            )
        )
    assert "missing_target_id_for_refinement" in str(excinfo.value)


def test_candidate_payload_extra_forbid():
    from pydantic import ValidationError
    from backend.api.modules.requirements_core.flow_refinement.schemas import FlowRefinementCandidatePayload

    valid_data = {
        "project_id": 1,
        "workspace_id": 2,
        "target_flow_id": 42,
        "target_flow_logical_uuid": "flow-uuid-42",
        "target_kind": "flow",
        "target_id": 42,
        "expected_workspace_version": "hash-123",
        "context_hash": "hash-123",
        "rationale": "Refined checkout",
        "steps_added": [],
        "transitions_added": [],
        "transitions_updated": [],
        "rules_added": [],
        "rule_links_added": [],
        "business_objects_added": [],
        "step_object_links_added": [],
    }
    payload = FlowRefinementCandidatePayload.model_validate(valid_data)
    assert payload.target_flow_id == 42

    # Extra attribute forbidden
    invalid_data = dict(valid_data, unauthorized_extra_field="malicious")
    with pytest.raises(ValidationError):
        FlowRefinementCandidatePayload.model_validate(invalid_data)
