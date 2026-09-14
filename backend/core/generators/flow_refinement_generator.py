"""LLM generator for bounded flow refinement and rule elaboration."""

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.core.generators.base_generator import BaseGenerator, GenerateInput
from backend.core.generators.prompts import flow_refinement_generate_prompt
from backend.core.prompt_resolver import get_content_locale


class _StepOutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    temp_id: str = Field(pattern=re.compile(r"^(?!existing_).+"))
    name: str
    description: str
    step_type: str = "actorAction"
    actor_ids: list[int] = Field(default_factory=list)
    input_business_object_numbers: list[str] = Field(default_factory=list)
    output_business_object_numbers: list[str] = Field(default_factory=list)


class _TransitionOutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    temp_id: str = Field(pattern=re.compile(r"^(?!existing_).+"))
    source_step_ref: str | int
    target_step_ref: str | int
    label: str
    condition_text: str = ""
    is_default: bool = False
    semantic_tags: list[str] = Field(default_factory=list)
    rule_refs: list[str] = Field(default_factory=list)


class _TransitionUpdateOutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    logical_uuid: str
    label: str | None = None
    condition_text: str | None = None
    semantic_tags: list[str] | None = None
    rule_refs: list[str] | None = None


class _RuleOutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    temp_id: str = Field(pattern=re.compile(r"^(?!existing_).+"))
    title: str
    statement: str
    parent_rule_ref: str | None = None
    confirmation_status: Literal["ai_assumption"] = "ai_assumption"
    source_links: list[dict[str, Any]] = Field(default_factory=list)


class _RuleLinkOutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_ref: str
    target_kind: str
    target_ref: str
    link_purpose: str = "applies_to"
    context_text: str | None = None


class _BusinessObjectOutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_object_number: str
    business_object_name: str
    business_object_description: str
    business_object_attributes: list[dict[str, Any]] = Field(default_factory=list)


class _FlowRefinementOutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rationale: str = ""
    steps_added: list[_StepOutputModel] = Field(default_factory=list)
    transitions_added: list[_TransitionOutputModel] = Field(default_factory=list)
    transitions_updated: list[_TransitionUpdateOutputModel] = Field(default_factory=list)
    rules_added: list[_RuleOutputModel] = Field(default_factory=list)
    rule_links_added: list[_RuleLinkOutputModel] = Field(default_factory=list)
    business_objects_added: list[_BusinessObjectOutputModel] = Field(default_factory=list)


@dataclass
class FlowRefinementGeneratorInput(GenerateInput):
    """Input payload for flow path refinement generator."""
    target_flow_name: str
    target_flow_description: str
    anchor_info: str
    existing_steps: list[dict[str, Any]] = field(default_factory=list)
    existing_transitions: list[dict[str, Any]] = field(default_factory=list)
    path_projection: dict[str, Any] = field(default_factory=dict)
    linked_requirements: dict[str, Any] = field(default_factory=dict)
    applicable_rules: list[dict[str, Any]] = field(default_factory=list)
    finding_context: str | None = None
    focus_text: str | None = None
    context_hash: str = ""
    knowledge_fragments: list[dict[str, Any]] = field(default_factory=list)
    refinement_scope: dict[str, Any] = field(default_factory=dict)


class FlowRefinementGenerator(BaseGenerator[FlowRefinementGeneratorInput]):
    """Generates bounded flow refinement candidates using LLMHandler."""

    @staticmethod
    def _reference_context(input_data: FlowRefinementGeneratorInput) -> tuple[dict, dict[str, str]]:
        """Use exact, short references in the prompt without exposing out-of-scope bindings."""
        data = asdict(input_data)
        scope = data["refinement_scope"]
        positions = scope.get("allowed_step_positions")
        transitions = scope.get("allowed_transition_uuids")
        local_steps = [s for s in data["existing_steps"] if positions is None or s["position"] in positions]
        local_transitions = [t for t in data["existing_transitions"] if transitions is None or t["logical_uuid"] in transitions]
        step_positions = {s["step_id"]: s["position"] for s in data["existing_steps"] if "step_id" in s}
        transition_refs = {t["transition_id"]: t["logical_uuid"] for t in local_transitions if "transition_id" in t}
        data["path_projection"] = {
            **data["path_projection"],
            "paths": [
                {
                    **{key: value for key, value in path.items() if key not in ("step_ids", "transition_ids")},
                    "step_positions": [step_positions[sid] for sid in path.get("step_ids", [])],
                    "transition_refs": [transition_refs[tid] for tid in path.get("transition_ids", []) if tid in transition_refs],
                }
                for path in data["path_projection"].get("paths", [])
            ],
        }
        for step in local_steps:
            step.pop("step_id", None)
        for transition in local_transitions:
            for key in ("transition_id", "source_step_id", "target_step_id"):
                transition.pop(key, None)
        # Retain the outer topology for orientation, not as an editable actor/object catalog.
        data["existing_steps"] = [
            s if s in local_steps else {"position": s["position"], "name": s["name"], "read_only": True}
            for s in data["existing_steps"]
        ]
        data["existing_transitions"] = local_transitions
        sources = {
            kind: data["linked_requirements"].get(key, [])
            for kind, key in (("feature", "features"), ("scenario", "scenarios"))
        }
        sources["knowledge"] = data["knowledge_fragments"]
        catalogs = {**sources, "flow_step": local_steps, "flow_transition": local_transitions, "rule": data["applicable_rules"]}
        references = {
            item["logical_uuid"]: f"existing_{kind}_{index}"
            for kind, items in catalogs.items()
            for index, item in enumerate(items, 1) if item.get("logical_uuid")
        }
        flow_uuid = scope.get("target_flow_logical_uuid")
        if flow_uuid:
            references[flow_uuid] = "existing_flow_1"
        valid_targets = {
            kind: {item["logical_uuid"] for item in items if item.get("logical_uuid")}
            for kind, items in catalogs.items()
        }
        valid_targets["flow"] = {flow_uuid} if flow_uuid else set()
        for rule in data["applicable_rules"]:
            rule["links"] = [
                link for link in rule.get("links", [])
                if link.get("target_logical_uuid") in valid_targets.get(link.get("target_kind"), set())
            ]
            if rule.get("parent_rule_uuid") not in valid_targets["rule"]:
                rule["parent_rule_uuid"] = None

        def encode(value):
            if isinstance(value, str):
                return references.get(value, value)
            if isinstance(value, list):
                return [encode(item) for item in value]
            if isinstance(value, dict):
                return {key: encode(item) for key, item in value.items()}
            return value

        return encode(data), {ref: uuid for uuid, ref in references.items()}

    @staticmethod
    def _resolve_references(output: dict, references: dict[str, str]) -> dict:
        """Resolve only reference fields; unknown identifiers remain errors, never guessed UUIDs."""
        reference_fields = {"logical_uuid", "parent_rule_ref", "rule_ref", "rule_refs", "target_ref", "target_logical_uuid", "source_step_ref", "target_step_ref"}

        def resolve(value, field=None):
            if isinstance(value, str) and field in reference_fields:
                return references.get(value, value)
            if isinstance(value, list):
                return [resolve(item, field) for item in value]
            if isinstance(value, dict):
                return {key: resolve(item, key) for key, item in value.items()}
            return value

        return resolve(output)

    async def generate(self, input_data: FlowRefinementGeneratorInput) -> dict:
        """Call LLM to produce candidate path refinement and validate output schema."""
        is_english = get_content_locale() == "en-US"
        context, references = self._reference_context(input_data)
        values = {
            "target_flow_name": input_data.target_flow_name,
            "target_flow_description": input_data.target_flow_description,
            "anchor_info": input_data.anchor_info,
            "existing_steps": json.dumps(context["existing_steps"], ensure_ascii=False, indent=2),
            "existing_transitions": json.dumps(context["existing_transitions"], ensure_ascii=False, indent=2),
            "path_projection": json.dumps(context["path_projection"], ensure_ascii=False, indent=2),
            "linked_requirements": json.dumps(context["linked_requirements"], ensure_ascii=False, indent=2),
            "applicable_rules": json.dumps(context["applicable_rules"], ensure_ascii=False, indent=2),
            "finding_context": input_data.finding_context or ("None" if is_english else "无"),
            "focus_text": input_data.focus_text or (
                "Identify key uncovered paths" if is_english else "无特别指定，全面识别关键未覆盖路径"
            ),
            "knowledge_fragments": json.dumps(context["knowledge_fragments"], ensure_ascii=False, indent=2),
            "refinement_scope": json.dumps(context["refinement_scope"], ensure_ascii=False, indent=2),
        }
        prompt = str(flow_refinement_generate_prompt)
        for name, value in values.items():
            prompt = prompt.replace("{{" + name + "}}", value)

        response = await self._llm_handler.call_llm(
            prompt=prompt,
            query="",
            print_log=False,
            raise_on_failure=True,
            protected_inputs=self._protected_inputs(input_data),
        )

        raw_json = self._extract_json_payload(response)
        validated = _FlowRefinementOutputModel.model_validate(raw_json)
        return self._resolve_references(validated.model_dump(), references)

    @staticmethod
    def _extract_json_payload(response: Any) -> dict:
        """Extract dictionary payload from LLM response."""
        if isinstance(response, dict):
            return response
        if isinstance(response, str):
            text = response.strip()
            if text.startswith("```"):
                lines = text.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                text = "\n".join(lines).strip()
            return json.loads(text)
        raise ValueError("invalid_llm_response_type")
