import re

from backend.core.detectors.issue_context_loader import IssueProjectContext
from backend.schemas import (
    ActorNode,
    BusinessObjectNode,
    FeatureNode,
    ScenarioNode,
)


class PerceptionDraftNormalizer:
    _step_number_pattern = re.compile(r"^S-\d{3}$")
    _valid_step_types = {
        "actorAction",
        "systemAction",
        "judgment",
    }

    @staticmethod
    def normalize_filled_actors(raw: dict | None) -> list[dict]:
        if raw is None:
            raise ValueError("empty_filler_response")

        raw_actors = raw.get("actors", [])

        if not raw_actors:
            raise ValueError("empty_actors")

        actors = []

        for item in raw_actors:
            actor_name = item.get("actor_name")
            actor_description = item.get("actor_description")

            if not actor_name or not actor_description:
                raise ValueError("invalid_actor_payload")

            actors.append(
                {
                    "actor_name": actor_name,
                    "actor_description": actor_description,
                }
            )

        return actors

    @staticmethod
    def normalize_filled_features(
        raw: dict | None,
        context: IssueProjectContext,
    ) -> list[dict]:
        if raw is None:
            raise ValueError("empty_filler_response")

        raw_features = raw.get("features", [])

        if not raw_features:
            raise ValueError("empty_features")

        existing_feature_ids = {
            feature.feature_id
            for feature in context.features
        }
        temporary_feature_ids = set()
        features = []

        for item in raw_features:
            temporary_feature_id = item.get("feature_id")
            feature_name = item.get("feature_name")
            feature_description = item.get("feature_description")
            parent_id = item.get("parent_id")

            if temporary_feature_id is None:
                raise ValueError("invalid_feature_payload")

            try:
                temporary_feature_id = int(temporary_feature_id)
            except (TypeError, ValueError) as error:
                raise ValueError("invalid_feature_payload") from error

            if temporary_feature_id in temporary_feature_ids:
                raise ValueError("duplicate_feature_id")

            if not feature_name or not feature_description:
                raise ValueError("invalid_feature_payload")

            if parent_id is None:
                raise ValueError("missing_parent_feature")

            try:
                parent_id = int(parent_id)
            except (TypeError, ValueError) as error:
                raise ValueError("missing_parent_feature") from error

            temporary_feature_ids.add(temporary_feature_id)
            features.append(
                {
                    "temporary_feature_id": temporary_feature_id,
                    "feature_name": feature_name,
                    "feature_description": feature_description,
                    "parent_temporary_feature_id": (
                        parent_id
                        if parent_id not in existing_feature_ids
                        else None
                    ),
                    "parent_feature_id": (
                        parent_id
                        if parent_id in existing_feature_ids
                        else None
                    ),
                }
            )

        for item in features:
            parent_temporary_feature_id = item["parent_temporary_feature_id"]

            if (
                parent_temporary_feature_id is not None
                and parent_temporary_feature_id not in temporary_feature_ids
            ):
                raise ValueError("missing_parent_feature")

        return features

    @staticmethod
    def normalize_filled_scenarios(
        raw: dict | None,
        actor: ActorNode,
        feature: FeatureNode,
    ) -> list[dict]:
        if raw is None:
            raise ValueError("empty_filler_response")

        raw_scenarios = raw.get("scenarios", [])

        if not raw_scenarios:
            raise ValueError("empty_scenarios")

        scenarios = []

        for item in raw_scenarios:
            scenario_name = item.get("scenario_name", "")
            scenario_content = item.get("scenario_content", "")

            if not scenario_name or not scenario_content:
                raise ValueError("invalid_scenario_payload")

            scenarios.append(
                {
                    "feature_id": feature.featureId,
                    "feature_name": feature.featureName,
                    "actor_id": actor.actorId,
                    "actor_name": actor.actorName,
                    "scenario_name": scenario_name,
                    "scenario_content": scenario_content,
                }
            )

        return scenarios

    @staticmethod
    def normalize_filled_acceptance_criteria(
        raw: dict | None,
        scenarios: list[ScenarioNode],
    ) -> list[dict]:
        if raw is None:
            raise ValueError("empty_filler_response")

        raw_items = raw.get("scenario_acceptance_criteria", [])

        if not raw_items:
            raise ValueError("empty_acceptance_criteria")

        scenario_name_map = {
            scenario.scenarioId: scenario.scenarioName
            for scenario in scenarios
        }
        seen_scenario_ids = set()
        result = []

        for item in raw_items:
            try:
                scenario_id = int(item.get("scenario_id"))
            except (TypeError, ValueError) as error:
                raise ValueError("invalid_scenario_reference") from error

            if scenario_id not in scenario_name_map:
                raise ValueError("invalid_scenario_reference")

            if scenario_id in seen_scenario_ids:
                raise ValueError("duplicate_scenario_id")

            seen_scenario_ids.add(scenario_id)
            raw_criteria = item.get("acceptance_criteria", [])

            if not isinstance(raw_criteria, list) or not raw_criteria:
                raise ValueError("empty_acceptance_criteria")

            acceptance_criteria = []

            for criterion in raw_criteria:
                if not isinstance(criterion, str):
                    raise ValueError("invalid_acceptance_criteria_payload")

                criterion = criterion.strip()

                if not criterion:
                    raise ValueError("invalid_acceptance_criteria_payload")

                acceptance_criteria.append(criterion)

            result.append(
                {
                    "scenario_id": scenario_id,
                    "scenario_name": scenario_name_map[scenario_id],
                    "acceptance_criteria": acceptance_criteria,
                }
            )

        return result

    @classmethod
    def normalize_filled_flow_payload(
        cls,
        raw: dict | None,
        context: IssueProjectContext,
        business_object_nodes: list[BusinessObjectNode],
    ) -> dict:
        if raw is None:
            raise ValueError("empty_filler_response")

        (
            business_objects,
            business_object_ref_map,
        ) = cls.normalize_filled_business_objects(
            raw.get("business_objects", []),
            business_object_nodes,
        )
        flows = cls.normalize_filled_flows(
            raw.get("flows", []),
            business_object_ref_map,
        )

        cls.validate_filled_flows(
            flows=flows,
            business_objects=business_objects,
            context=context,
            business_object_nodes=business_object_nodes,
        )

        return {
            "business_objects": business_objects,
            "flows": flows,
        }

    @classmethod
    def _normalize_flow_step_numbers(
        cls,
        raw_steps: list[dict],
    ) -> tuple[list[dict], dict[object, str], set[str]]:
        aliases = {}
        used_numbers = set()
        normalized_steps = []
        for index, step in enumerate(raw_steps, start=1):
            if not isinstance(step, dict):
                raise ValueError("invalid_flow_step_payload")
            raw_number = step.get("step_number")
            number = cls.normalize_step_number(raw_number, index)
            if number in used_numbers:
                number = cls.next_available_step_number(
                    index,
                    used_numbers,
                )
            used_numbers.add(number)
            for alias in {
                raw_number,
                "" if raw_number is None else str(raw_number),
                number,
            }:
                if alias != "":
                    aliases[alias] = number
            normalized_steps.append({**step, "step_number": number})
        return normalized_steps, aliases, used_numbers

    @classmethod
    def _normalize_flow_step_references(
        cls,
        step: dict,
        business_object_ref_map: dict[object, int],
        step_aliases: dict[object, str],
        step_numbers: set[str],
    ) -> None:
        step["step_type"] = cls.normalize_step_type(step.get("step_type"))
        step["actor_ids"] = cls.dedupe_int_values(
            step.get("actor_ids", [])
        )
        step["input_business_object_ids"] = (
            cls.dedupe_business_object_refs(
                cls.coerce_list(
                    step.get("input_business_object_ids", [])
                )
                + cls.coerce_list(
                    step.get("input_business_object_numbers", [])
                ),
                business_object_ref_map,
            )
        )
        step["output_business_object_ids"] = (
            cls.dedupe_business_object_refs(
                cls.coerce_list(
                    step.get("output_business_object_ids", [])
                )
                + cls.coerce_list(
                    step.get("output_business_object_numbers", [])
                ),
                business_object_ref_map,
            )
        )

    @classmethod
    def _normalize_filled_flow(
        cls,
        flow: dict,
        business_object_ref_map: dict[object, int],
    ) -> dict:
        if not isinstance(flow, dict):
            raise ValueError("invalid_flow_payload")
        raw_steps = flow.get("flow_steps", [])
        if not isinstance(raw_steps, list) or not raw_steps:
            raise ValueError("empty_flow_steps")
        steps, aliases, step_numbers = cls._normalize_flow_step_numbers(
            raw_steps
        )
        for step in steps:
            cls._normalize_flow_step_references(
                step,
                business_object_ref_map,
                aliases,
                step_numbers,
            )
        transitions = cls.normalize_transitions(
            flow.get("transitions", []),
            aliases,
            step_numbers,
        )
        return {
            **flow,
            "feature_ids": cls.dedupe_int_values(
                flow.get("feature_ids", [])
            ),
            "flow_steps": steps,
            "transitions": transitions,
        }

    @classmethod
    def normalize_filled_flows(
        cls,
        raw_flows: list[dict],
        business_object_ref_map: dict[object, int],
    ) -> list[dict]:
        if not isinstance(raw_flows, list) or not raw_flows:
            raise ValueError("empty_flows")

        return [
            cls._normalize_filled_flow(
                flow,
                business_object_ref_map,
            )
            for flow in raw_flows
        ]

    @classmethod
    def normalize_step_number(
        cls,
        value: object,
        fallback_index: int,
    ) -> str:
        if isinstance(value, str):
            stripped = value.strip().upper()
            if cls._step_number_pattern.match(stripped) is not None:
                return stripped

            match = re.match(r"^S-?(\d+)$", stripped)
            if match:
                return f"S-{int(match.group(1)):03d}"

            if stripped.isdigit():
                return f"S-{int(stripped):03d}"

        if isinstance(value, int):
            return f"S-{value:03d}"

        return f"S-{fallback_index:03d}"

    @classmethod
    def next_available_step_number(
        cls,
        preferred_index: int,
        used_step_numbers: set[str],
    ) -> str:
        index = preferred_index

        while True:
            step_number = f"S-{index:03d}"

            if step_number not in used_step_numbers:
                return step_number

            index += 1

    @staticmethod
    def normalize_step_type(value: object) -> object:
        if not isinstance(value, str):
            return value

        normalized = re.sub(r"[^a-z]", "", value.lower())
        aliases = {
            "actoraction": "actorAction",
            "actor": "actorAction",
            "useraction": "actorAction",
            "systemaction": "systemAction",
            "system": "systemAction",
            "judgment": "judgment",
            "decision": "judgment",
            "condition": "judgment",
        }

        return aliases.get(normalized, value)

    @staticmethod
    def coerce_list(value: object) -> list:
        if value is None:
            return []

        if isinstance(value, list):
            return value

        return [value]

    @classmethod
    def dedupe_int_values(cls, values: object) -> list[int]:
        result = []
        seen = set()

        for value in cls.coerce_list(values):
            try:
                int_value = int(value)
            except (TypeError, ValueError):
                continue

            if int_value in seen:
                continue

            seen.add(int_value)
            result.append(int_value)

        return result

    @classmethod
    def dedupe_business_object_refs(
        cls,
        values: object,
        business_object_ref_map: dict[object, int],
    ) -> list[int]:
        result = []
        seen = set()

        for value in cls.coerce_list(values):
            business_object_id = (
                business_object_ref_map.get(value)
                or business_object_ref_map.get(str(value))
            )

            if business_object_id is None:
                try:
                    business_object_id = int(value)
                except (TypeError, ValueError):
                    continue

            if business_object_id in seen:
                continue

            seen.add(business_object_id)
            result.append(business_object_id)

        return result

    @classmethod
    def normalize_transitions(
        cls,
        values: object,
        step_aliases: dict[object, str],
        step_number_set: set[str],
    ) -> list[dict]:
        result = []
        for item in cls.coerce_list(values):
            if not isinstance(item, dict):
                continue
            src = (
                step_aliases.get(item.get("source_step_number"))
                or step_aliases.get(str(item.get("source_step_number")))
                or cls.normalize_step_number(item.get("source_step_number"), 0)
            )
            tgt = (
                step_aliases.get(item.get("target_step_number"))
                or step_aliases.get(str(item.get("target_step_number")))
                or cls.normalize_step_number(item.get("target_step_number"), 0)
            )
            if src in step_number_set and tgt in step_number_set and src != tgt:
                result.append({
                    "source_step_number": src,
                    "target_step_number": tgt,
                    "label": item.get("label", ""),
                    "condition_text": item.get("condition_text", ""),
                    "is_default": bool(item.get("is_default", False)),
                    "position": int(item.get("position", 0)),
                    "semantic_tags": cls.coerce_list(
                        item.get("semantic_tags", [])
                    ),
                })
        return result

    @staticmethod
    def _build_business_object_reference_map(
        existing_business_object_ids: set[int],
    ) -> dict[object, int]:
        reference_map = {}
        for business_object_id in existing_business_object_ids:
            reference_map[business_object_id] = business_object_id
            reference_map[str(business_object_id)] = business_object_id
        return reference_map

    @staticmethod
    def _normalize_business_object_id(
        reference,
        seen_ids: set[int],
        next_temporary_id: int,
    ) -> tuple[int, int]:
        try:
            business_object_id = int(reference)
        except (TypeError, ValueError):
            while next_temporary_id in seen_ids:
                next_temporary_id -= 1
            business_object_id = next_temporary_id
            next_temporary_id -= 1
        if business_object_id in seen_ids:
            raise ValueError("duplicate_business_object_id")
        seen_ids.add(business_object_id)
        return business_object_id, next_temporary_id

    @staticmethod
    def _register_business_object_references(
        reference_map: dict[object, int],
        item: dict,
        reference,
        business_object_id: int,
    ) -> None:
        reference_map[reference] = business_object_id
        reference_map[str(reference)] = business_object_id
        number = item.get("business_object_number")
        if number is not None:
            reference_map[number] = business_object_id
            reference_map[str(number)] = business_object_id

    @staticmethod
    def _normalize_business_object_attributes(item: dict) -> list[dict]:
        payload = item.get("business_object_attributes", [])
        if payload is None:
            payload = []
        if not isinstance(payload, list):
            raise ValueError("invalid_business_object_payload")
        attributes = []
        for attribute in payload:
            if not isinstance(attribute, dict):
                raise ValueError("invalid_business_object_payload")
            name = attribute.get("business_object_attribute_name", "")
            description = attribute.get(
                "business_object_attribute_description",
                "",
            )
            data_type = attribute.get(
                "business_object_attribute_type",
                "",
            )
            example = attribute.get(
                "business_object_attribute_example",
                "",
            )
            if not name or not description or not data_type:
                raise ValueError("invalid_business_object_payload")
            attributes.append(
                {
                    "business_object_attribute_name": name,
                    "business_object_attribute_description": description,
                    "business_object_attribute_type": data_type,
                    "business_object_attribute_example": (
                        "" if example is None else str(example)
                    ),
                }
            )
        return attributes

    @classmethod
    def normalize_filled_business_objects(
        cls,
        raw_items: list[dict],
        business_object_nodes: list[BusinessObjectNode],
    ) -> tuple[list[dict], dict[object, int]]:
        if not isinstance(raw_items, list):
            raise ValueError("invalid_business_object_payload")
        existing_ids = {
            item.businessObjectId
            for item in business_object_nodes
        }
        reference_map = cls._build_business_object_reference_map(
            existing_ids
        )
        seen_ids = set()
        business_objects = []
        next_temporary_id = -1
        for item in raw_items:
            if not isinstance(item, dict):
                raise ValueError("invalid_business_object_payload")
            reference = (
                item.get("business_object_id")
                if item.get("business_object_id") is not None
                else item.get("business_object_number")
            )
            if reference is None:
                raise ValueError("invalid_business_object_payload")
            business_object_id, next_temporary_id = (
                cls._normalize_business_object_id(
                    reference,
                    seen_ids,
                    next_temporary_id,
                )
            )
            cls._register_business_object_references(
                reference_map,
                item,
                reference,
                business_object_id,
            )
            name = item.get("business_object_name", "")
            description = item.get("business_object_description", "")
            if not name or not description:
                raise ValueError("invalid_business_object_payload")
            business_objects.append(
                {
                    "business_object_id": business_object_id,
                    "business_object_name": name,
                    "business_object_description": description,
                    "is_existing": business_object_id in existing_ids,
                    "business_object_attributes": (
                        cls._normalize_business_object_attributes(item)
                    ),
                }
            )
        return business_objects, reference_map

    @classmethod
    def _validate_filled_flow_header(
        cls,
        flow: dict,
        feature_ids: set[int],
    ) -> tuple[list[dict], set[str]]:
        if not isinstance(flow, dict):
            raise ValueError("invalid_flow_payload")
        if not flow.get("flow_name") or not flow.get("flow_description"):
            raise ValueError("invalid_flow_payload")
        referenced_feature_ids = flow.get("feature_ids", [])
        if not referenced_feature_ids:
            raise ValueError("invalid_feature_reference")
        for feature_id in referenced_feature_ids:
            if feature_id not in feature_ids:
                raise ValueError("invalid_feature_reference")
        steps = flow.get("flow_steps", [])
        if not steps:
            raise ValueError("empty_flow_steps")
        step_numbers = [step.get("step_number") for step in steps]
        step_number_set = set(step_numbers)
        if len(step_number_set) != len(step_numbers):
            raise ValueError("duplicate_step_number")
        for number in step_numbers:
            if (
                not isinstance(number, str)
                or cls._step_number_pattern.match(number) is None
            ):
                raise ValueError("invalid_step_number_format")
        return steps, step_number_set

    @classmethod
    def _validate_filled_flow_step(
        cls,
        step: dict,
        *,
        actor_ids: set[int],
        business_object_ids: set[int],
        step_numbers: set[str],
    ) -> None:
        if step.get("step_type") not in cls._valid_step_types:
            raise ValueError("invalid_step_type")
        if not step.get("step_name") or not step.get("step_description"):
            raise ValueError("invalid_flow_step_payload")
        for actor_id in step.get("actor_ids", []):
            if actor_id not in actor_ids:
                raise ValueError("invalid_actor_reference")
        for business_object_id in step.get(
            "input_business_object_ids",
            [],
        ):
            if business_object_id not in business_object_ids:
                raise ValueError("invalid_business_object_reference")
        for business_object_id in step.get(
            "output_business_object_ids",
            [],
        ):
            if business_object_id not in business_object_ids:
                raise ValueError("invalid_business_object_reference")

    @classmethod
    def validate_filled_flows(
        cls,
        flows: list[dict],
        business_objects: list[dict],
        context: IssueProjectContext,
        business_object_nodes: list[BusinessObjectNode],
    ) -> None:
        actor_id_set = {
            actor.actor_id
            for actor in context.actors
        }
        feature_id_set = {
            feature.feature_id
            for feature in context.features
        }
        business_object_id_set = {
            item.businessObjectId
            for item in business_object_nodes
        } | {
            item["business_object_id"]
            for item in business_objects
        }

        for flow in flows:
            flow_steps, step_numbers = cls._validate_filled_flow_header(
                flow,
                feature_id_set,
            )
            for step in flow_steps:
                cls._validate_filled_flow_step(
                    step,
                    actor_ids=actor_id_set,
                    business_object_ids=business_object_id_set,
                    step_numbers=step_numbers,
                )
