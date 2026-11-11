import pytest
from backend.core.generators.flows_generator import FlowsGenerator, FlowsGeneratorInput
from backend.api.modules.requirements_core.flow.application.flow_generation_service import FlowGenerationService
from backend.schemas import ActorNode, FeatureNode


def test_flows_generator_serialize_prompt_context_assigns_rule_number():
    gen = FlowsGenerator()
    input_data = FlowsGeneratorInput(
        user_requirements="Test requirements",
        actors=[ActorNode(actorId=1, actorName="User", actorDescription="Regular User")],
        features=[FeatureNode(featureId=1, featureName="Feature 1", featureDescription="F1")],
        rules=[
            {
                "id": 101,
                "logical_uuid": "uuid-rule-001",
                "title": "Rule One",
                "statement": "Statement One",
                "confirmation_status": "confirmed",
                "links": [],
            },
            {
                "id": 102,
                "logical_uuid": "uuid-rule-002",
                "title": "Rule Two",
                "statement": "Statement Two",
                "confirmation_status": "ai_assumption",
                "links": [],
            },
        ],
    )
    _, _, rules_json, _, _ = gen._serialize_prompt_context(input_data)
    assert '"rule_number": "R-001"' in rules_json
    assert '"rule_number": "R-002"' in rules_json
    assert '"logical_uuid": "uuid-rule-001"' in rules_json
    assert '"logical_uuid": "uuid-rule-002"' in rules_json


def test_flows_generator_normalize_rule_references_maps_short_ids_and_discards_hallucinations():
    rules = [
        {"id": 10, "logical_uuid": "rule-uuid-alpha", "title": "Rule Alpha"},
        {"id": 20, "logical_uuid": "rule-uuid-beta", "title": "Rule Beta"},
    ]
    raw = {
        "flows": [
            {
                "flow_name": "Main Flow",
                # R-001 should resolve to alpha, hallucinated uuid should be discarded
                "rule_refs": ["R-001", "ba5d2998-7b6a-40a8-8fdc-a63b46700d85", "R-001"],
                "flow_steps": [
                    {
                        "step_number": "S-001",
                        # r-2 should resolve to beta, rule_id '10' to alpha
                        "rule_refs": ["r-002", "10", "unknown-temp-id"],
                    }
                ],
                "transitions": [
                    {
                        "source_step_number": "S-001",
                        "target_step_number": "S-002",
                        # direct uuid should stay, R-002 should resolve
                        "rule_refs": ["rule-uuid-beta", "R-001"],
                    }
                ],
            }
        ]
    }

    normalized = FlowsGenerator._normalize_rule_references(raw, rules)
    flow = normalized["flows"][0]
    # flow rule_refs: R-001 -> rule-uuid-alpha; hallucinated discarded; duplicates removed
    assert flow["rule_refs"] == ["rule-uuid-alpha"]

    # step rule_refs: r-002 -> beta, 10 -> alpha, unknown discarded
    step = flow["flow_steps"][0]
    assert step["rule_refs"] == ["rule-uuid-beta", "rule-uuid-alpha"]

    # transition rule_refs: beta stays, R-001 -> alpha
    transition = flow["transitions"][0]
    assert transition["rule_refs"] == ["rule-uuid-beta", "rule-uuid-alpha"]


def test_flow_generation_service_sanitize_rule_references():
    valid_rule_uuids = {"uuid-1", "uuid-2"}
    raw = {
        "flows": [
            {
                "flow_name": "Test Flow",
                "rule_refs": ["uuid-1", "invalid-hallucinated-uuid"],
                "flow_steps": [
                    {
                        "step_number": "S-001",
                        "rule_refs": ["uuid-2", "not-a-valid-rule"],
                    }
                ],
                "transitions": [
                    {
                        "source_step_number": "S-001",
                        "target_step_number": "S-002",
                        "rule_refs": ["uuid-1", "ba5d2998-7b6a-40a8-8fdc-a63b46700d85"],
                    }
                ],
            }
        ]
    }

    FlowGenerationService._sanitize_rule_references(raw, valid_rule_uuids)
    flow = raw["flows"][0]
    assert flow["rule_refs"] == ["uuid-1"]
    assert flow["flow_steps"][0]["rule_refs"] == ["uuid-2"]
    assert flow["transitions"][0]["rule_refs"] == ["uuid-1"]


def test_flows_generator_loads_llm_json_repairs_expecting_colon_error():
    # String with unescaped internal quotes that triggers "Expecting ':' delimiter"
    # in standard json.loads:
    malformed = '{"flow_name": "Test", "condition_text": "user clicks "confirm" button", "items": [1, 2,]}'
    # standard json.loads fails:
    with pytest.raises(Exception):
        import json
        json.loads(malformed)

    # But _loads_llm_json repairs it gracefully:
    res = FlowsGenerator._loads_llm_json(malformed)
    assert isinstance(res, dict)
    assert res["flow_name"] == "Test"
    assert "confirm" in res["condition_text"]


def test_flows_generator_loads_llm_json_handles_codeblocks():
    wrapped = "```json\n{\"flow_name\": \"Flow 1\", \"flows\": []}\n```"
    res = FlowsGenerator._loads_llm_json(wrapped)
    assert isinstance(res, dict)
    assert res["flow_name"] == "Flow 1"
