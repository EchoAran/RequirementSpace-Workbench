import re

import pytest

from backend.api.modules.requirements_core.flow.application.generation.validation import validate_flow
from backend.api.modules.requirements_core.flow_refinement.application.normalizer import normalize_and_validate_refinement
from backend.api.modules.requirements_core.flow.application.choice_adapter import FlowGenerationChoiceAdapter
from backend.api.modules.decision_workflow.ports.ports import GenerationCandidate


@pytest.mark.parametrize("kind", ["flow", "step", "transition"])
@pytest.mark.parametrize("refs", [["unknown"], "rule-1", [[]], {}])
def test_generated_rule_references_validated_at_every_scope(kind, refs):
    flow = {
        "feature_ids": [1], "rule_refs": ["rule-1"],
        "flow_steps": [{"step_number": "S-001", "step_type": "actorAction", "rule_refs": ["rule-1"]},
                       {"step_number": "S-002", "step_type": "systemAction"}],
        "transitions": [{"source_step_number": "S-001", "target_step_number": "S-002", "rule_refs": ["rule-1"]}],
    }
    target = flow if kind == "flow" else flow["flow_steps" if kind == "step" else "transitions"][0]
    target["rule_refs"] = refs
    with pytest.raises(ValueError, match=f"invalid_{kind}_rule_ref"):
        validate_flow(flow, step_number_pattern=re.compile(r"^S-\d{3}$"), valid_step_types={"actorAction", "systemAction"},
                      valid_actor_ids=set(), valid_feature_ids={1}, valid_business_object_numbers=set(),
                      valid_rule_uuids={"rule-1"})


@pytest.mark.parametrize("target_kind,flow_ref,valid", [
    ("flow", "flow-1", True), ("flow", "other-flow", False), ("flow_step", "flow-1", False),
])
def test_refinement_flow_associations_respect_anchor_scope(target_kind, flow_ref, valid):
    raw = {"rule_links_added": [{"rule_ref": "rule-1", "target_kind": "flow", "target_ref": flow_ref}]}
    args = dict(existing_step_positions={1}, existing_step_uuids={"step-1"}, existing_transition_uuids=set(),
                existing_rule_uuids={"rule-1"}, confirmed_rule_statements=set(), existing_flow_uuid="flow-1",
                target_kind=target_kind)
    if valid:
        assert normalize_and_validate_refinement(raw, **args)["rule_links_added"][0]["target_kind"] == "flow"
    else:
        with pytest.raises(ValueError, match="invalid_rule_link_flow_target"):
            normalize_and_validate_refinement(raw, **args)


def test_generation_dedup_keeps_candidates_with_different_rule_scopes():
    def candidate(flow_rule, step_rules):
        return GenerationCandidate(title="Order", rationale="Order", payload={"flows": [{
            "flow_name": "Order", "rule_refs": flow_rule,
            "flow_steps": [{"step_number": "S-001", "rule_refs": step_rules}],
        }]})
    adapter = FlowGenerationChoiceAdapter()
    step_candidate = candidate([], ["rule-1"])
    assert not adapter.is_duplicate(candidate(["rule-1"], []), [step_candidate])
    assert adapter.is_duplicate(candidate([], ["rule-1", "rule-1"]), [step_candidate])
