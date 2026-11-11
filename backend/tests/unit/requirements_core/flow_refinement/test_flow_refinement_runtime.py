import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, create_autospec, patch

import pytest

from backend.api.modules.decision_workflow.ports.ports import GenerationCandidate
from backend.api.modules.requirements_core.flow_refinement.application.choice_adapter import (
    FlowRefinementChoiceAdapter,
)
from backend.api.modules.requirements_core.flow_refinement.application.context_loader import (
    compute_refinement_context_hash,
)
from backend.api.modules.requirements_core.flow_refinement.application.normalizer import (
    normalize_and_validate_refinement,
)
from backend.api.modules.requirements_core.flow_refinement.domain.invariants import validate_refinement_references
from backend.core.generators.flow_refinement_generator import (
    FlowRefinementGenerator,
    FlowRefinementGeneratorInput,
)
from backend.core.llm_context import LLMRequestContext, current_llm_context
from backend.services.llm_handler_service import LLMCallFailedError, LLMHandler


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", ["zh-CN", "en-US"])
async def test_real_prompt_and_generator_use_supported_handler_contract(locale):
    token = current_llm_context.set(LLMRequestContext("unused", "unused", "unused", locale))
    try:
        generator = FlowRefinementGenerator()
        generator._llm_handler = create_autospec(LLMHandler, instance=True)
        generator._llm_handler.call_llm.return_value = json.dumps({"rationale": "complete"})
        result = await generator.generate(FlowRefinementGeneratorInput(
            target_flow_name="Checkout",
            target_flow_description="Order flow",
            anchor_info="Step 1",
            linked_requirements={"scenarios": [{"content": "Scenario body"}]},
        ))
        assert result["steps_added"] == []
        kwargs = generator._llm_handler.call_llm.call_args.kwargs
        assert kwargs["raise_on_failure"] is True
        assert "{{" not in kwargs["prompt"]
        assert "Checkout" in kwargs["prompt"]
        assert "Scenario body" in kwargs["prompt"]
        if locale == "en-US":
            assert "无" not in kwargs["prompt"]
    finally:
        current_llm_context.reset(token)


@pytest.mark.asyncio
async def test_generator_propagates_model_failure():
    generator = FlowRefinementGenerator()
    generator._llm_handler = create_autospec(LLMHandler, instance=True)
    generator._llm_handler.call_llm.side_effect = LLMCallFailedError("upstream failed")
    with pytest.raises(LLMCallFailedError, match="upstream failed"):
        await generator.generate(FlowRefinementGeneratorInput("Flow", "Body", "Step 1"))


@pytest.mark.asyncio
async def test_stale_check_matches_public_adapter_contract_and_keeps_finding_source():
    adapter = FlowRefinementChoiceAdapter()
    choice = SimpleNamespace(payload={
        "project_id": 1, "target_flow_id": 10, "context_hash": "same",
        "expected_workspace_version": "same", "target_kind": "flow", "target_id": 10,
        "workspace_id": 2, "source_finding_id": "finding-1",
    })
    with patch(
        "backend.api.modules.requirements_core.flow_refinement.application.choice_adapter.load_flow_refinement_context",
        new=AsyncMock(return_value=SimpleNamespace(context_hash="same")),
    ) as load:
        assert await adapter.is_context_stale(choice, AsyncMock()) == (False, None)
        assert load.call_args.kwargs["source_finding_id"] == "finding-1"


@pytest.mark.parametrize("key,first,second", [
    ("rules_added", {"title": "Rule A"}, {"title": "Rule B"}),
    ("transitions_updated", {"logical_uuid": "t1", "label": "A"}, {"logical_uuid": "t1", "label": "B"}),
    ("business_objects_added", {"business_object_name": "Order"}, {"business_object_name": "Invoice"}),
    ("transitions_added", {"label": "Branch", "condition_text": "A"}, {"label": "Branch", "condition_text": "B"}),
])
def test_distinct_non_step_changes_are_not_deduplicated(key, first, second):
    adapter = FlowRefinementChoiceAdapter()
    a = GenerationCandidate("A", "", {key: [first]})
    b = GenerationCandidate("B", "", {key: [second]})
    assert adapter.is_duplicate(a, [b]) is False


def test_transition_rule_refs_and_duplicate_source_links_are_normalized():
    result = normalize_and_validate_refinement(
        {
            "transitions_updated": [{"logical_uuid": "t1", "rule_refs": ["r-new"]}],
            "rules_added": [{
                "temp_id": "r-new", "title": "Rule", "statement": "Evidence rule",
                "source_links": [
                    {"target_kind": "scenario", "target_ref": "sc1", "context_text": "short"},
                    {"target_kind": "scenario", "target_logical_uuid": "sc1", "context_text": "stronger evidence"},
                ],
            }],
            "rule_links_added": [{"rule_ref": "r-new", "target_kind": "flow_transition", "target_ref": "t1"}],
        },
        existing_step_positions={1, 2}, existing_step_uuids={"s1", "s2"},
        existing_transition_uuids={"t1"}, existing_rule_uuids=set(),
        confirmed_rule_statements=set(), context_scenario_uuids={"sc1"},
    )
    assert len(result["rules_added"][0]["source_links"]) == 1
    assert result["rules_added"][0]["source_links"][0]["context_text"] == "stronger evidence"
    assert len(result["rule_links_added"]) == 1


def test_transition_rule_refs_cannot_silently_reference_missing_rules():
    with pytest.raises(ValueError, match="invalid_rule_link_rule_reference"):
        normalize_and_validate_refinement(
            {"transitions_updated": [{"logical_uuid": "t1", "rule_refs": ["missing"]}]},
            existing_step_positions=set(), existing_step_uuids=set(),
            existing_transition_uuids={"t1"}, existing_rule_uuids=set(),
            confirmed_rule_statements=set(),
        )


@pytest.mark.parametrize("context_key,old,new", [
    ("actors", {"id": 1, "name": "Buyer", "description": "Old"}, {"id": 1, "name": "Buyer", "description": "New"}),
    ("business_objects", {"id": 1, "name": "Order", "attributes": [{"name": "amount", "data_type": "int"}]}, {"id": 1, "name": "Order", "attributes": [{"name": "amount", "data_type": "float"}]}),
])
def test_context_hash_tracks_scoped_catalog_content(context_key, old, new):
    assert compute_refinement_context_hash("flow", "Flow", [], [], [], [], **{context_key: [old]}) != compute_refinement_context_hash("flow", "Flow", [], [], [], [], **{context_key: [new]})


@pytest.mark.parametrize("response", [None, "not JSON", "[]", '{"unexpected": true}'])
@pytest.mark.asyncio
async def test_generator_rejects_invalid_response_without_fabricating_success(response):
    generator = FlowRefinementGenerator()
    generator._llm_handler = create_autospec(LLMHandler, instance=True)
    generator._llm_handler.call_llm.return_value = response
    with pytest.raises(ValueError):
        await generator.generate(FlowRefinementGeneratorInput("Flow", "Body", "Step 1"))


def scoped_reference_input(local=True):
    return FlowRefinementGeneratorInput(
        "Flow", "Body", "Step 3",
        existing_steps=[
            {"step_id": 7, "position": 1, "name": "Upload", "logical_uuid": "step-uuid-1", "actor_ids": [8]},
            {"step_id": 9, "position": 3, "name": "Extract", "logical_uuid": "step-uuid-3", "actor_ids": []},
        ],
        existing_transitions=[{"transition_id": 11, "logical_uuid": "transition-uuid", "source_step_id": 7, "target_step_id": 9, "source_step_position": 1, "target_step_position": 3}],
        path_projection={"paths": [{"path_id": "main", "step_ids": [7, 9], "transition_ids": [11], "is_main": True}]},
        linked_requirements={
            "features": [{"logical_uuid": "feature-uuid", "name": "Feature"}],
            "scenarios": [{"logical_uuid": "scenario-uuid", "name": "Extraction", "content": "Scenario"}],
        },
        applicable_rules=[{
            "logical_uuid": "rule-uuid", "title": "Rule", "statement": "Check extraction",
            "parent_rule_uuid": "outside-parent",
            "links": [
                {"target_kind": "scenario", "target_logical_uuid": "scenario-uuid", "link_purpose": "source"},
                {"target_kind": "scenario", "target_logical_uuid": "outside-scenario", "link_purpose": "source"},
                {"target_kind": "flow_step", "target_logical_uuid": "step-uuid-1", "link_purpose": "applies_to"},
            ],
        }],
        knowledge_fragments=[{"logical_uuid": "chunk-1", "content": "Knowledge"}],
        refinement_scope={
            "target_kind": "flow_step" if local else "flow", "target_flow_logical_uuid": "flow-uuid",
            "allowed_step_positions": [3] if local else None,
            "allowed_step_uuids": ["step-uuid-3"] if local else None,
            "allowed_transition_uuids": [] if local else None,
            "actors": [] if local else [{"id": 8, "name": "User"}], "business_objects": [],
        },
    )


@pytest.mark.parametrize("local", [True, False])
def test_prompt_reference_context_only_exposes_selectable_bindings_without_mutating_input(local):
    original = scoped_reference_input(local)
    context, references = FlowRefinementGenerator._reference_context(original)
    assert original.existing_steps[0]["actor_ids"] == [8]
    assert original.applicable_rules[0]["links"][1]["target_logical_uuid"] == "outside-scenario"
    assert context["linked_requirements"]["scenarios"][0]["logical_uuid"] == "existing_scenario_1"
    assert references["existing_scenario_1"] == "scenario-uuid"
    assert context["applicable_rules"][0]["parent_rule_uuid"] is None
    assert "outside-scenario" not in json.dumps(context)
    assert context["path_projection"]["paths"][0]["step_positions"] == [1, 3]
    assert '"step_id"' not in json.dumps(context)
    assert '"step_ids"' not in json.dumps(context)
    assert '"target_step_id"' not in json.dumps(context)
    if local:
        assert context["existing_steps"][0] == {"position": 1, "name": "Upload", "read_only": True}
        assert context["existing_transitions"] == []
        assert context["path_projection"]["paths"][0]["transition_refs"] == []
        assert len(context["applicable_rules"][0]["links"]) == 1
        assert context["refinement_scope"]["actors"] == []
    else:
        assert context["existing_steps"][0]["actor_ids"] == [8]
        assert len(context["existing_transitions"]) == 1
        assert context["path_projection"]["paths"][0]["transition_refs"] == ["existing_flow_transition_1"]


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", ["zh-CN", "en-US"])
async def test_generator_resolves_exact_evidence_and_target_references_but_not_prose(locale):
    token = current_llm_context.set(LLMRequestContext("unused", "unused", "unused", locale))
    try:
        generator = FlowRefinementGenerator()
        generator._llm_handler = create_autospec(LLMHandler, instance=True)
        generator._llm_handler.call_llm.return_value = json.dumps({
            "rationale": "existing_scenario_1",
            "steps_added": [{"temp_id": "s-new", "name": "Extract", "description": "Extract", "actor_ids": []}],
            "transitions_added": [{"temp_id": "t-new", "source_step_ref": "existing_flow_step_1", "target_step_ref": "s-new", "label": "Branch", "rule_refs": ["existing_rule_1"]}],
            "rules_added": [{
                "temp_id": "r-new", "title": "Check", "statement": "Check", "parent_rule_ref": "existing_rule_1",
                "source_links": [{"target_kind": "scenario", "target_ref": "existing_scenario_1", "context_text": "existing_scenario_1"}],
            }],
            "rule_links_added": [{"rule_ref": "r-new", "target_kind": "flow_step", "target_ref": "existing_flow_step_1"}],
        })
        result = await generator.generate(scoped_reference_input())
        assert result["rationale"] == "existing_scenario_1"
        assert result["rules_added"][0]["parent_rule_ref"] == "rule-uuid"
        assert result["rules_added"][0]["source_links"][0]["target_ref"] == "scenario-uuid"
        assert result["rules_added"][0]["source_links"][0]["context_text"] == "existing_scenario_1"
        assert result["transitions_added"][0]["source_step_ref"] == "step-uuid-3"
        assert result["transitions_added"][0]["rule_refs"] == ["rule-uuid"]
        assert result["rule_links_added"][0]["target_ref"] == "step-uuid-3"
        prompt = generator._llm_handler.call_llm.call_args.kwargs["prompt"]
        assert '"actor_ids": [8]' not in prompt
        assert "scenario-uuid" not in prompt
        assert "outside-scenario" not in prompt
        assert "step-uuid-1" not in prompt
        validate_refinement_references(
            result["steps_added"], result["transitions_added"], [], result["rules_added"], result["rule_links_added"],
            existing_step_positions={3}, existing_step_uuids={"step-uuid-3"}, existing_transition_uuids=set(),
            existing_rule_uuids={"rule-uuid"}, allowed_actor_ids=set(), context_scenario_uuids={"scenario-uuid"},
        )
    finally:
        current_llm_context.reset(token)


@pytest.mark.parametrize("case", ["scenario", "actor"])
def test_invalid_model_references_are_not_repaired_or_silently_dropped(case):
    _, references = FlowRefinementGenerator._reference_context(scoped_reference_input())
    output = FlowRefinementGenerator._resolve_references({
        "steps_added": [{"temp_id": "s-new", "actor_ids": [8] if case == "actor" else []}],
        "rules_added": [{"temp_id": "r-new", "source_links": [{"target_kind": "scenario", "target_ref": "58f0a2a0-0000-0000-0000-000000000000"}]}] if case == "scenario" else [],
    }, references)
    with pytest.raises(ValueError, match="step_actor_outside_local_refinement_radius" if case == "actor" else "rule_source_link_not_in_context"):
        validate_refinement_references(
            output["steps_added"], [], [], output["rules_added"], [],
            existing_step_positions={3}, existing_step_uuids={"step-uuid-3"}, existing_transition_uuids=set(),
            existing_rule_uuids=set(), allowed_actor_ids=set(), context_scenario_uuids={"scenario-uuid"},
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["steps_added", "transitions_added", "rules_added"])
async def test_new_entities_cannot_shadow_existing_reference_namespace(kind):
    generator = FlowRefinementGenerator()
    generator._llm_handler = create_autospec(LLMHandler, instance=True)
    generator._llm_handler.call_llm.return_value = json.dumps({kind: [{"temp_id": "existing_scenario_1"}]})
    with pytest.raises(ValueError, match="string_pattern_mismatch"):
        await generator.generate(scoped_reference_input())
