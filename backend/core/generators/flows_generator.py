import json
from dataclasses import dataclass, field
from typing import Any

from backend.core.generators.base_generator import BaseGenerator, GenerateInput
from backend.core.generators.prompts import (
    business_object_in_flows_prompt,
    business_objects_generate_prompt,
    flows_generate_combined_prompt,
    flows_generate_prompt,
)
from backend.schemas import ActorNode, FeatureNode


@dataclass
class FlowsGeneratorInput(GenerateInput):
    user_requirements: str
    actors: list[ActorNode]
    features: list[FeatureNode]
    rules: list[dict[str, Any]] = field(default_factory=list)
    scenarios: list[dict[str, Any]] = field(default_factory=list)
    acceptance_criteria: list[dict[str, Any]] = field(default_factory=list)
    context_hash: str = ""
    user_feedback: str | None = None


class FlowsGenerator(BaseGenerator[FlowsGeneratorInput]):
    """Generates business flows and object specifications using LLMHandler."""

    async def generate(
        self,
        input_data: FlowsGeneratorInput,
        use_combined_prompt: bool = False,
    ) -> dict:
        (
            actors,
            features,
            rules,
            scenarios,
            acceptance_criteria,
        ) = self._serialize_prompt_context(input_data)
        if use_combined_prompt:
            raw = await self._generate_combined(
                input_data,
                actors,
                features,
                rules,
                scenarios,
                acceptance_criteria,
            )
        else:
            raw = await self._generate_sequential(
                input_data,
                actors,
                features,
                rules,
                scenarios,
                acceptance_criteria,
            )
        return self._normalize_rule_references(raw, input_data.rules)

    @staticmethod
    def _serialize_prompt_context(
        input_data: FlowsGeneratorInput,
    ) -> tuple[str, str, str, str, str]:
        actors_payload = ActorNode.schema(
            many=True,
            only=("actorId", "actorName", "actorDescription"),
        ).dump(input_data.actors)
        actors = json.dumps(
            {"actors": actors_payload},
            ensure_ascii=False,
            indent=2,
        )
        features_payload = FeatureNode.schema(
            many=True,
            only=("featureId", "featureName", "featureDescription", "actorIds"),
        ).dump(node for node in input_data.features if len(node.childrenIds) == 0)
        features = json.dumps(
            {"features": features_payload},
            ensure_ascii=False,
            indent=2,
        )
        rules_payload = [
            {
                "rule_number": f"R-{idx:03d}",
                "rule_id": r.get("id"),
                "logical_uuid": r.get("logical_uuid"),
                "title": r.get("title"),
                "statement": r.get("statement"),
                "confirmation_status": r.get("confirmation_status"),
                "parent_rule_uuid": r.get("parent_rule_uuid"),
                "source_links": [
                    {
                        "target_kind": lnk.get("target_kind"),
                        "target_logical_uuid": lnk.get("target_logical_uuid"),
                        "link_purpose": lnk.get("link_purpose"),
                        "context_text": lnk.get("context_text", ""),
                    }
                    for lnk in (r.get("links") or r.get("source_links") or [])
                ],
            }
            for idx, r in enumerate(input_data.rules, start=1)
        ]
        rules = json.dumps(
            {"rules": rules_payload},
            ensure_ascii=False,
            indent=2,
        )
        scenarios_payload = [
            {
                "scenario_id": s.get("id"),
                "logical_uuid": s.get("logical_uuid"),
                "feature_id": s.get("feature_id"),
                "actor_id": s.get("actor_id"),
                "name": s.get("name"),
                "content": s.get("content"),
            }
            for s in input_data.scenarios
        ]
        scenarios = json.dumps(
            {"scenarios": scenarios_payload},
            ensure_ascii=False,
            indent=2,
        )
        ac_payload = [
            {
                "ac_id": ac.get("id"),
                "logical_uuid": ac.get("logical_uuid"),
                "scenario_id": ac.get("scenario_id"),
                "content": ac.get("content"),
            }
            for ac in input_data.acceptance_criteria
        ]
        acceptance_criteria = json.dumps(
            {"acceptance_criteria": ac_payload},
            ensure_ascii=False,
            indent=2,
        )
        return actors, features, rules, scenarios, acceptance_criteria

    async def _generate_combined(
        self,
        input_data: FlowsGeneratorInput,
        actors: str,
        features: str,
        rules: str,
        scenarios: str,
        acceptance_criteria: str,
    ) -> dict:
        response = await self._llm_handler.call_llm(
            prompt=flows_generate_combined_prompt.replace(
                "{{user_requirements}}", f"{input_data.user_requirements}"
            )
            .replace("{{actors}}", f"{actors}")
            .replace("{{features}}", f"{features}")
            .replace("{{scenarios}}", f"{scenarios}")
            .replace("{{acceptance_criteria}}", f"{acceptance_criteria}")
            .replace("{{rules}}", f"{rules}"),
            query=input_data.user_feedback or "",
            print_log=False,
            raise_on_failure=True,
            protected_inputs=self._protected_inputs(input_data),
        )
        result = self._loads_llm_json(response)
        if not isinstance(result, dict):
            raise ValueError("invalid_llm_response")
        return result

    async def _generate_sequential(
        self,
        input_data: FlowsGeneratorInput,
        actors: str,
        features: str,
        rules: str,
        scenarios: str,
        acceptance_criteria: str,
    ) -> dict:
        user_requirements = input_data.user_requirements
        feedback = input_data.user_feedback or ""
        flows_response = await self._llm_handler.call_llm(
            prompt=flows_generate_prompt.replace(
                "{{user_requirements}}", f"{user_requirements}"
            )
            .replace("{{actors}}", f"{actors}")
            .replace("{{features}}", f"{features}")
            .replace("{{scenarios}}", f"{scenarios}")
            .replace("{{acceptance_criteria}}", f"{acceptance_criteria}")
            .replace("{{rules}}", f"{rules}"),
            query=feedback,
            print_log=False,
            raise_on_failure=True,
            protected_inputs=self._protected_inputs(input_data),
        )
        flows_result = self._loads_llm_json(flows_response)
        if not isinstance(flows_result, dict):
            raise ValueError("invalid_llm_response")

        flows_ = self._dumps_prompt_payload(
            {"flows": flows_result.get("flows", [])}
        )

        business_objects_response = await self._llm_handler.call_llm(
            prompt=business_objects_generate_prompt.replace(
                "{{user_requirements}}", f"{user_requirements}"
            ).replace("{{flows}}", flows_),
            query=feedback,
            print_log=False,
            raise_on_failure=True,
            protected_inputs=self._protected_inputs(input_data),
        )
        business_objects_result = self._loads_llm_json(business_objects_response)
        if not isinstance(business_objects_result, dict):
            raise ValueError("invalid_llm_response")

        business_objects_ = self._dumps_prompt_payload(
            {
                "business_objects": business_objects_result.get(
                    "business_objects",
                    [],
                )
            }
        )

        relations_response = await self._llm_handler.call_llm(
            prompt=business_object_in_flows_prompt.replace(
                "{{user_requirements}}", f"{user_requirements}"
            )
            .replace("{{flows}}", flows_)
            .replace("{{business_objects}}", business_objects_),
            query=feedback,
            print_log=False,
            raise_on_failure=True,
            protected_inputs=self._protected_inputs(input_data),
        )
        relations_result = self._loads_llm_json(relations_response)

        return self._merge_generation_results(
            flows_result=flows_result,
            business_objects_result=business_objects_result,
            relations_result=relations_result,
        )

    @staticmethod
    def _loads_llm_json(response: str | None) -> Any:
        if response is None:
            raise ValueError("empty_llm_response")
        text = response.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        try:
            return json.loads(text)
        except Exception:
            try:
                import json_repair

                repaired = json_repair.loads(text)
                if isinstance(repaired, (dict, list)):
                    return repaired
            except Exception:
                pass
            return json.loads(text)

    @staticmethod
    def _dumps_prompt_payload(payload: dict) -> str:
        return json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )

    @staticmethod
    def _merge_generation_results(
        flows_result: dict,
        business_objects_result: dict,
        relations_result: Any,
    ) -> dict:
        flows = flows_result.get("flows")
        if not isinstance(flows, list):
            raise ValueError("invalid_flows_structure: 'flows' must be a list")

        business_objects = business_objects_result.get("business_objects")
        if not isinstance(business_objects, list):
            raise ValueError(
                "invalid_business_objects_structure: 'business_objects' must be a list"
            )

        if isinstance(relations_result, dict):
            relations = relations_result.get("business_object_in_flows")
            if relations is None:
                relations = relations_result.get("flows")
        else:
            relations = relations_result

        if not isinstance(relations, list):
            raise ValueError(
                "invalid_relations_structure: expected list of flow object relations"
            )

        relation_by_flow_name = {
            relation.get("flow_name"): relation
            for relation in relations
            if isinstance(relation, dict) and relation.get("flow_name")
        }

        for flow_index, flow in enumerate(flows):
            if not isinstance(flow, dict):
                raise ValueError("invalid_flow_item: expected dictionary")

            relation = relation_by_flow_name.get(flow.get("flow_name"))
            if relation is None and flow_index < len(relations):
                relation = relations[flow_index]

            step_relation_by_number = {}
            if isinstance(relation, dict):
                step_relation_by_number = {
                    step_relation.get("step_number"): step_relation
                    for step_relation in relation.get("flow_steps", [])
                    if (
                        isinstance(step_relation, dict)
                        and step_relation.get("step_number")
                    )
                }

            for step in flow.get("flow_steps", []):
                if not isinstance(step, dict):
                    raise ValueError("invalid_step_item: expected dictionary")

                step_relation = step_relation_by_number.get(
                    step.get("step_number"),
                    {},
                )
                step["input_business_object_numbers"] = step_relation.get(
                    "input_business_object_numbers",
                    [],
                )
                step["output_business_object_numbers"] = step_relation.get(
                    "output_business_object_numbers",
                    [],
                )

        return {
            "business_objects": business_objects,
            "flows": flows,
        }

    @classmethod
    def _normalize_rule_references(
        cls,
        raw: dict,
        rules: list[dict[str, Any]],
    ) -> dict:
        """Map rule references (short rule numbers, rule IDs, or UUIDs) back to canonical logical_uuids.

        Discards any hallucinated or unmapped references to prevent generation failures.
        """
        ref_to_uuid: dict[str, str] = {}
        for idx, r in enumerate(rules, start=1):
            uuid = r.get("logical_uuid")
            if not uuid:
                continue
            uuid_str = str(uuid).strip()
            ref_to_uuid[uuid_str] = uuid_str
            ref_to_uuid[uuid_str.lower()] = uuid_str

            # Short identifiers: R-001, R-1, r-001, r-1
            rule_num = f"R-{idx:03d}"
            ref_to_uuid[rule_num] = uuid_str
            ref_to_uuid[rule_num.lower()] = uuid_str
            ref_to_uuid[f"R-{idx}"] = uuid_str
            ref_to_uuid[f"r-{idx}"] = uuid_str
            ref_to_uuid[str(idx)] = uuid_str

            # Also by rule_id if present
            rule_id = r.get("id") or r.get("rule_id")
            if rule_id is not None:
                ref_to_uuid[str(rule_id)] = uuid_str

        def _resolve_refs(refs: Any) -> list[str]:
            if not isinstance(refs, list):
                return []
            resolved: list[str] = []
            for ref in refs:
                if ref is None:
                    continue
                key = str(ref).strip()
                target_uuid = ref_to_uuid.get(key) or ref_to_uuid.get(key.lower())
                if target_uuid and target_uuid not in resolved:
                    resolved.append(target_uuid)
            return resolved

        for flow in raw.get("flows", []):
            if not isinstance(flow, dict):
                continue
            flow["rule_refs"] = _resolve_refs(flow.get("rule_refs"))
            for step in flow.get("flow_steps", []):
                if isinstance(step, dict):
                    step["rule_refs"] = _resolve_refs(step.get("rule_refs"))
            for transition in flow.get("transitions", []):
                if isinstance(transition, dict):
                    transition["rule_refs"] = _resolve_refs(transition.get("rule_refs"))

        return raw

