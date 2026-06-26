import re
from backend.core.detectors.issue_context_loader import IssueProjectContext
from backend.schemas import (
    ActorNode,
    FeatureNode,
    ScenarioNode,
    BusinessObjectNode,
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
    def normalize_filled_flows(
        cls,
        raw_flows: list[dict],
        business_object_ref_map: dict[object, int],
    ) -> list[dict]:
        if not isinstance(raw_flows, list) or not raw_flows:
            raise ValueError("empty_flows")

        flows = []

        for flow in raw_flows:
            if not isinstance(flow, dict):
                raise ValueError("invalid_flow_payload")

            raw_steps = flow.get("flow_steps", [])

            if not isinstance(raw_steps, list) or not raw_steps:
                raise ValueError("empty_flow_steps")

            step_aliases: dict[object, str] = {}
            used_step_numbers: set[str] = set()
            normalized_steps = []

            for index, step in enumerate(raw_steps, start=1):
                if not isinstance(step, dict):
                    raise ValueError("invalid_flow_step_payload")

                raw_step_number = step.get("step_number")
                step_number = cls.normalize_step_number(
                    raw_step_number,
                    index,
                )

                if step_number in used_step_numbers:
                    step_number = cls.next_available_step_number(
                        index,
                        used_step_numbers,
                    )

                used_step_numbers.add(step_number)

                for alias in {
                    raw_step_number,
                    "" if raw_step_number is None else str(raw_step_number),
                    step_number,
                }:
                    if alias != "":
                        step_aliases[alias] = step_number

                normalized_steps.append(
                    {
                        **step,
                        "step_number": step_number,
                    }
                )

            for step in normalized_steps:
                step["step_type"] = cls.normalize_step_type(
                    step.get("step_type")
                )
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
                step["next_steps"] = cls.normalize_next_steps(
                    step.get("next_steps", []),
                    step_aliases,
                    used_step_numbers,
                )

            flows.append(
                {
                    **flow,
                    "feature_ids": cls.dedupe_int_values(
                        flow.get("feature_ids", [])
                    ),
                    "flow_steps": normalized_steps,
                }
            )

        return flows

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
    def normalize_next_steps(
        cls,
        values: object,
        step_aliases: dict[object, str],
        step_number_set: set[str],
    ) -> list[str]:
        result = []
        seen = set()

        for value in cls.coerce_list(values):
            step_number = (
                step_aliases.get(value)
                or step_aliases.get(str(value))
                or cls.normalize_step_number(value, 0)
            )

            if step_number not in step_number_set or step_number in seen:
                continue

            seen.add(step_number)
            result.append(step_number)

        return result

    @classmethod
    def normalize_filled_business_objects(
        cls,
        raw_items: list[dict],
        business_object_nodes: list[BusinessObjectNode],
    ) -> tuple[list[dict], dict[object, int]]:
        if not isinstance(raw_items, list):
            raise ValueError("invalid_business_object_payload")

        existing_business_object_ids = {
            item.businessObjectId
            for item in business_object_nodes
        }
        business_object_ref_map: dict[object, int] = {}

        for business_object_id in existing_business_object_ids:
            business_object_ref_map[business_object_id] = business_object_id
            business_object_ref_map[str(business_object_id)] = (
                business_object_id
            )

        seen_business_object_ids = set()
        business_objects = []
        next_temporary_business_object_id = -1

        for item in raw_items:
            if not isinstance(item, dict):
                raise ValueError("invalid_business_object_payload")

            business_object_ref = (
                item.get("business_object_id")
                if item.get("business_object_id") is not None
                else item.get("business_object_number")
            )

            if business_object_ref is None:
                raise ValueError("invalid_business_object_payload")

            try:
                business_object_id = int(business_object_ref)
            except (TypeError, ValueError):
                while (
                    next_temporary_business_object_id
                    in seen_business_object_ids
                ):
                    next_temporary_business_object_id -= 1

                business_object_id = next_temporary_business_object_id
                next_temporary_business_object_id -= 1

            if business_object_id in seen_business_object_ids:
                raise ValueError("duplicate_business_object_id")

            seen_business_object_ids.add(business_object_id)
            business_object_ref_map[business_object_ref] = business_object_id
            business_object_ref_map[str(business_object_ref)] = (
                business_object_id
            )

            business_object_number = item.get("business_object_number")

            if business_object_number is not None:
                business_object_ref_map[business_object_number] = (
                    business_object_id
                )
                business_object_ref_map[str(business_object_number)] = (
                    business_object_id
                )

            business_object_name = item.get("business_object_name", "")
            business_object_description = item.get(
                "business_object_description",
                "",
            )

            if not business_object_name or not business_object_description:
                raise ValueError("invalid_business_object_payload")

            attributes = []

            attributes_payload = item.get(
                "business_object_attributes",
                [],
            )

            if attributes_payload is None:
                attributes_payload = []

            if not isinstance(attributes_payload, list):
                raise ValueError("invalid_business_object_payload")

            for attribute in attributes_payload:
                if not isinstance(attribute, dict):
                    raise ValueError("invalid_business_object_payload")

                attribute_name = attribute.get(
                    "business_object_attribute_name",
                    "",
                )
                attribute_description = attribute.get(
                    "business_object_attribute_description",
                    "",
                )
                attribute_type = attribute.get(
                    "business_object_attribute_type",
                    "",
                )
                attribute_example = attribute.get(
                    "business_object_attribute_example",
                    "",
                )

                if (
                    not attribute_name
                    or not attribute_description
                    or not attribute_type
                ):
                    raise ValueError("invalid_business_object_payload")

                attributes.append(
                    {
                        "business_object_attribute_name": attribute_name,
                        "business_object_attribute_description": (
                            attribute_description
                        ),
                        "business_object_attribute_type": attribute_type,
                        "business_object_attribute_example": (
                            ""
                            if attribute_example is None
                            else str(attribute_example)
                        ),
                    }
                )

            business_objects.append(
                {
                    "business_object_id": business_object_id,
                    "business_object_name": business_object_name,
                    "business_object_description": (
                        business_object_description
                    ),
                    "is_existing": (
                        business_object_id in existing_business_object_ids
                    ),
                    "business_object_attributes": attributes,
                }
            )

        return business_objects, business_object_ref_map

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
            if not isinstance(flow, dict):
                raise ValueError("invalid_flow_payload")

            if not flow.get("flow_name") or not flow.get(
                "flow_description"
            ):
                raise ValueError("invalid_flow_payload")

            feature_ids = flow.get("feature_ids", [])

            if not feature_ids:
                raise ValueError("invalid_feature_reference")

            for feature_id in feature_ids:
                if feature_id not in feature_id_set:
                    raise ValueError("invalid_feature_reference")

            flow_steps = flow.get("flow_steps", [])

            if not flow_steps:
                raise ValueError("empty_flow_steps")

            step_numbers = [
                step.get("step_number")
                for step in flow_steps
            ]
            step_number_set = set(step_numbers)

            if len(step_number_set) != len(step_numbers):
                raise ValueError("duplicate_step_number")

            for step_number in step_numbers:
                if (
                    not isinstance(step_number, str)
                    or cls._step_number_pattern.match(step_number) is None
                ):
                    raise ValueError("invalid_step_number_format")

            for step in flow_steps:
                step_type = step.get("step_type")

                if step_type not in cls._valid_step_types:
                    raise ValueError("invalid_step_type")

                if not step.get("step_name") or not step.get(
                    "step_description"
                ):
                    raise ValueError("invalid_flow_step_payload")

                for actor_id in step.get("actor_ids", []):
                    if actor_id not in actor_id_set:
                        raise ValueError("invalid_actor_reference")

                for business_object_id in step.get(
                    "input_business_object_ids",
                    [],
                ):
                    if business_object_id not in business_object_id_set:
                        raise ValueError(
                            "invalid_business_object_reference"
                        )

                for business_object_id in step.get(
                    "output_business_object_ids",
                    [],
                ):
                    if business_object_id not in business_object_id_set:
                        raise ValueError(
                            "invalid_business_object_reference"
                        )

                for next_step_number in step.get("next_steps", []):
                    if next_step_number not in step_number_set:
                        raise ValueError("invalid_next_step_reference")
