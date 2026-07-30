from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.core.issue_resolution.fingerprint import load_target_entity_snapshot
from backend.core.issue_resolution.generation_draft_solver import (
    GenerationDraftIssueSolver,
)
from backend.core.issue_resolution.validator import RepairValidator
from backend.core.generators.flows_generator import (
    FlowsGenerator,
    FlowsGeneratorInput,
)
from backend.core.suggestions import what_suggestion_policy as suggestion_module
from backend.core.suggestions.what_suggestion_policy import WhatSuggestionPolicy
from backend.schemas import ActorNode, FeatureNode
from backend.schemas import IssueTarget


class _QueryResult:
    def __init__(self, *, scalar=None, rows=None):
        self._scalar = scalar
        self._rows = rows or []

    def scalar_one_or_none(self):
        return self._scalar

    def fetchall(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


@pytest.mark.asyncio
async def test_validate_domain_preserves_mixed_patch_checks_and_query_order():
    validator = RepairValidator()
    validator._entity_exists = AsyncMock(return_value=True)
    validator._assert_leaf_feature = AsyncMock()
    session = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _QueryResult(),
                _QueryResult(),
                _QueryResult(),
            ]
        )
    )
    patch = {
        "updateNodes": [
            {"kind": "scope", "id": 1, "reason": "Keep the scope explicit"},
            {"kind": "scenario", "id": 2, "feature_id": 3},
        ],
        "addLinks": [
            {
                "type": "feature_actor_relation",
                "source_id": 4,
                "target_id": 5,
            },
            {
                "type": "flow_feature_relation",
                "source_id": 6,
                "target_id": 7,
            },
        ],
        "addNodes": [
            {
                "kind": "business_object_attribute",
                "name": "status",
                "data_type": "string",
                "business_object_id": 8,
            }
        ],
    }

    await validator.validate_domain(10, "IGNORED_BY_CURRENT_RULES", patch, session)

    assert validator._entity_exists.await_args_list == [
        ((10, "feature", 3, session),),
        ((10, "flow", 6, session),),
        ((10, "feature", 7, session),),
        ((10, "business_object", 8, session),),
    ]
    validator._assert_leaf_feature.assert_awaited_once_with(10, 4, session)
    assert session.execute.await_count == 3


@pytest.mark.asyncio
async def test_feature_snapshot_preserves_fields_and_actor_order():
    feature = SimpleNamespace(
        id=12,
        name="Checkout",
        description="Complete an order",
    )
    session = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _QueryResult(scalar=feature),
                _QueryResult(rows=[(9,), (4,)]),
            ]
        )
    )

    snapshot = await load_target_entity_snapshot(3, "feature", 12, session)

    assert snapshot == {
        "project_id": 3,
        "target_type": "feature",
        "target_id": 12,
        "name": "Checkout",
        "description": "Complete an order",
        "actor_ids": [9, 4],
    }
    assert session.execute.await_count == 2


@pytest.mark.asyncio
async def test_generation_draft_fallback_preserves_pair_payload_and_contract():
    resolution = await GenerationDraftIssueSolver().resolve(
        project_id=3,
        issue_code="FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO",
        target=IssueTarget(
            targetType="feature_actor_pair",
            targetId="12:9",
        ),
        metadata={"issue_id": "issue-1", "stage": "what"},
        session=SimpleNamespace(),
    )

    assert resolution.to_dict() == {
        "kind": "issue_resolution",
        "issue_code": "FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO",
        "resolution_type": "generation_draft",
        "title": "生成场景草稿",
        "description": "为该功能与参与者组合创建场景草稿。",
        "action": {
            "kind": "create_draft",
            "draft_type": "scenario_generation",
            "endpoint": "/api/scenario_generation_drafts/{draft_id}/confirm",
            "payload": {
                "project_id": 3,
                "issue_id": "issue-1",
                "stage": "what",
                "feature_id": 12,
                "actor_id": 9,
            },
        },
        "draft_id": None,
        "draft": {},
        "patch": None,
    }


@pytest.mark.asyncio
async def test_what_suggestion_preserves_priority_and_public_project_id(
    monkeypatch,
):
    context = SimpleNamespace(
        actors=[SimpleNamespace()],
        features=[SimpleNamespace()],
        leaf_features=[
            SimpleNamespace(
                feature_id=12,
                name="Checkout",
                actor_ids=[],
            )
        ],
        scenarios=[],
    )
    monkeypatch.setattr(
        suggestion_module,
        "load_issue_project_context",
        AsyncMock(return_value=context),
    )

    suggestion = await WhatSuggestionPolicy().get_next(
        project_id=3,
        session=SimpleNamespace(),
        public_project_id="project-public-id",
    )

    assert suggestion.code == "BIND_ACTORS_TO_FEATURE"
    assert suggestion.target == {"type": "feature", "id": 12}
    assert suggestion.action == {
        "kind": "open_panel",
        "route": "/projects/project-public-id/what",
        "panel": "feature",
        "payload": {"feature_id": 12},
    }


@pytest.mark.asyncio
async def test_flows_generator_preserves_three_step_merge_contract():
    generator = FlowsGenerator()
    generator._llm_handler = SimpleNamespace(
        call_llm=AsyncMock(
            side_effect=[
                '{"flows":[{"flow_name":"Checkout","flow_steps":[{"step_number":1}]}]}',
                '{"business_objects":[{"business_object_number":1,"name":"Order"}]}',
                (
                    '{"business_object_in_flows":[{"flow_name":"Checkout",'
                    '"flow_steps":[{"step_number":1,'
                    '"input_business_object_numbers":[1],'
                    '"output_business_object_numbers":[]}]}]}'
                ),
            ]
        )
    )
    input_data = FlowsGeneratorInput(
        user_requirements="Support checkout",
        actors=[
            ActorNode(
                actorId=7,
                actorName="Buyer",
                actorDescription="Places orders",
            )
        ],
        features=[
            FeatureNode(
                featureId=12,
                featureName="Checkout",
                featureDescription="Complete an order",
                actorIds=[7],
            ),
            FeatureNode(
                featureId=13,
                featureName="Commerce",
                featureDescription="Parent feature",
                childrenIds=[12],
            ),
        ],
        user_feedback="Keep it concise",
    )

    result = await generator.generate(input_data)

    assert result == {
        "business_objects": [
            {"business_object_number": 1, "name": "Order"},
        ],
        "flows": [
            {
                "flow_name": "Checkout",
                "flow_steps": [
                    {
                        "step_number": 1,
                        "input_business_object_numbers": [1],
                        "output_business_object_numbers": [],
                    }
                ],
            }
        ],
    }
    assert generator._llm_handler.call_llm.await_count == 3
    for call in generator._llm_handler.call_llm.await_args_list:
        assert call.kwargs["query"] == "Keep it concise"
    first_prompt = generator._llm_handler.call_llm.await_args_list[0].kwargs["prompt"]
    assert "Checkout" in first_prompt
    assert "Commerce" not in first_prompt
