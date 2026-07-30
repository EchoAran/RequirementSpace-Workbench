from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple


def escape_string(text: str | None) -> str:
    if not text:
        return ""
    # Clean up non-printable characters (except common ones)
    cleaned = "".join(ch for ch in text if ch.isprintable() or ch in "\n\r\t")
    # Escape quotes
    escaped = cleaned.replace('"', '\\"')
    # Replace newlines with spaces to keep strings single-line in SPL literals
    escaped = escaped.replace('\r\n', ' ').replace('\n', ' ')
    # Collapse multiple spaces
    escaped = re.sub(r'\s+', ' ', escaped)
    return escaped.strip()


class SplSyntaxRenderer:
    """
    Deterministic renderer to convert RequirementSpace project detail response
    into a valid SPL syntax shell document.
    """

    def __init__(self) -> None:
        pass

    def render(self, payload: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:
        warnings: List[Dict[str, Any]] = []
        trace_links: List[Dict[str, Any]] = []

        project = payload.get("project", {})
        project_name = project.get("project_name", "Unknown")
        project_id = project.get("project_id", "00000000")
        project_desc = project.get("project_description", "")
        user_reqs = project.get("user_requirements", "")
        is_english = payload.get("export_options", {}).get("language") == "en-US"

        safe_project_id = re.sub(r'[^a-zA-Z0-9]', '', project_id)[:8]
        if not safe_project_id:
            safe_project_id = "project"

        actors = payload.get("actors", [])
        lines = self._build_project_header(
            safe_project_id,
            project_name,
            project_desc,
            user_reqs,
            actors,
        )
        if not actors:
            warnings.append({
                "code": "empty_actors",
                "message": "Project has no actors defined.",
                "source": {"kind": "project", "id": project_id}
            })

        # 4. CONSTRAINTS (Delivery Scopes and Unresolved Gates)
        features = payload.get("features", [])
        unresolved_gates = payload.get("unresolved_gates", [])
        self._append_constraints(
            lines, warnings, features, unresolved_gates, project_id, is_english
        )

        # 5. TYPES (Business Objects)
        business_objects = payload.get("business_objects", [])
        if not business_objects:
            warnings.append({
                "code": "empty_business_objects",
                "message": "Project has no business objects defined.",
                "source": {"kind": "project", "id": project_id}
            })
        self._append_business_object_types(lines, warnings, business_objects)

        # 6. VARIABLES (Features catalog)
        if not features:
            warnings.append({
                "code": "empty_features",
                "message": "Project has no features defined.",
                "source": {"kind": "project", "id": project_id}
            })
            
        self._append_feature_variables(lines, features)

        # 7. WORKERS (Flows)
        flows = payload.get("flows", [])
        if not flows:
            warnings.append({
                "code": "empty_flows",
                "message": "Project has no flows defined.",
                "source": {"kind": "project", "id": project_id}
            })
        self._append_flow_workers(lines, trace_links, flows, features)

        lines.append("[END_AGENT]")
        spl_text = "\n".join(lines) + "\n"

        return spl_text, warnings, trace_links

    @staticmethod
    def _build_project_header(
        safe_project_id,
        project_name,
        project_description,
        user_requirements,
        actors,
    ) -> list[str]:
        lines = [
            f"[DEFINE_AGENT: Agent_{safe_project_id} "
            f"\"RequirementSpace SPL syntax export for "
            f"{escape_string(project_name)}\"]",
            "[DEFINE_PERSONA:]",
            f"ROLE: Requirement specification agent for the exported "
            f"requirement space {escape_string(project_name)}.",
            f"DOMAIN: {escape_string(project_name)}",
            "[END_PERSONA]",
            "",
            "[DEFINE_AUDIENCE:]",
        ]
        for actor in actors:
            lines.append(
                f"Actor_{actor.get('actor_id')}: "
                f"\"{escape_string(actor.get('actor_name', ''))}: "
                f"{escape_string(actor.get('actor_description', ''))}\""
            )
        lines.extend([
            "[END_AUDIENCE]",
            "",
            "[DEFINE_CONCEPTS:]",
            f"ProjectDescription: \"{escape_string(project_description)}\"",
            f"UserRequirements: \"{escape_string(user_requirements)}\"",
            "[END_CONCEPTS]",
            "",
        ])
        return lines

    @staticmethod
    def _append_constraints(
        lines, warnings, features, unresolved_gates, project_id, is_english
    ) -> None:
        lines.append("[DEFINE_CONSTRAINTS:]")
        for feature in features:
            feature_id = feature.get("feature_id")
            feature_name = feature.get("feature_name", "")
            scope = feature.get("scope") or {}
            status = scope.get("scope_status")
            reason = scope.get("reason", "")
            is_leaf = not feature.get("children_ids", [])
            if not status:
                status = "current"
                if is_leaf:
                    warnings.append({
                        "code": "missing_scope",
                        "message": f"Leaf feature Feature_{feature_id} '{feature_name}' is missing scope status.",
                        "source": {"kind": "feature", "id": str(feature_id)},
                    })
            status_map = {
                "current": "current" if is_english else "current (本期)",
                "postponed": "postponed" if is_english else "postponed (暂缓)",
                "exclude": "excluded" if is_english else "exclude (不纳入)",
            }
            status_text = status_map.get(status, status)
            reason_text = f" Reason: {escape_string(reason)}" if reason else ""
            lines.append(
                f"DeliveryScope: \"Feature_{feature_id} {escape_string(feature_name)} "
                f"is {status_text}.{reason_text}\""
            )
        for gate in unresolved_gates:
            code = gate.get("code") or gate.get("finding_id", "gate")
            detail = "" if is_english else f": {escape_string(gate.get('description', ''))}"
            lines.append(
                f"ExportGate: \"Unresolved gate {escape_string(code)}{detail}\""
            )
            warnings.append({
                "code": "unresolved_gate",
                "message": f"Export includes unresolved gate: {code}.",
                "source": {"kind": "project", "id": project_id},
            })
        lines.extend(["[END_CONSTRAINTS]", ""])

    @classmethod
    def _append_business_object_types(
        cls, lines, warnings, business_objects
    ) -> None:
        lines.append("[DEFINE_TYPES:]")
        for business_object in business_objects:
            object_id = business_object.get("business_object_id")
            name = business_object.get("business_object_name", "")
            description = business_object.get("business_object_description", "")
            lines.append(
                f"\"BusinessObject {escape_string(name)}: "
                f"{escape_string(description)}\""
            )
            lines.append(f"BusinessObject_{object_id} = {{")
            attributes = [
                cls._render_attribute(attribute, object_id, warnings)
                for attribute in business_object.get(
                    "business_object_attributes", []
                )
            ]
            lines.append(",\n".join(attributes))
            lines.append("}")
        lines.extend(["[END_TYPES]", ""])

    @staticmethod
    def _render_attribute(attribute, object_id, warnings) -> str:
        name = attribute.get("business_object_attribute_name", "")
        description = attribute.get(
            "business_object_attribute_description", ""
        )
        attr_type = attribute.get(
            "business_object_attribute_type", "string"
        ).lower()
        example = attribute.get("business_object_attribute_example", "")
        safe_name = re.sub(r"[^a-zA-Z0-9_]", "", name)
        if not safe_name:
            safe_name = (
                f"field_{attribute.get('business_object_attribute_id')}"
            )
        type_map = {
            "string": "text",
            "text": "text",
            "datetime": "text",
            "integer": "number",
            "int": "number",
            "number": "number",
            "float": "number",
            "bool": "boolean",
            "boolean": "boolean",
            "array[string]": "List [text]",
            "array[number]": "List [number]",
        }
        spl_type = type_map.get(attr_type)
        if spl_type is None:
            spl_type = "text"
            warnings.append({
                "code": "unsupported_type",
                "message": f"Unsupported attribute type '{attr_type}' mapped to 'text'.",
                "source": {
                    "kind": "business_object",
                    "id": str(object_id),
                },
            })
        comment = (
            f"\"Description: {escape_string(description)}. "
            f"Example: {escape_string(example)}\" "
            if description or example else ""
        )
        return f"  {comment}{safe_name}: {spl_type}"

    @staticmethod
    def _append_feature_variables(lines, features) -> None:
        lines.append("[DEFINE_VARIABLES:]")
        for feature in features:
            feature_id = feature.get("feature_id")
            name = feature.get("feature_name", "")
            description = feature.get("feature_description", "")
            status = (
                (feature.get("scope") or {}).get("scope_status")
                or "current"
            )
            parent_id = feature.get("parent_id")
            children = feature.get("children_ids", [])
            parent = f"Feature_{parent_id}" if parent_id else "None"
            children_text = (
                ", ".join(f"Feature_{child}" for child in children)
                if children else "None"
            )
            variable_description = (
                f"Description: {escape_string(description)}. Scope: {status}. "
                f"Parent: {parent}. Children: [{children_text}]."
            )
            lines.append(f"\"Feature: {escape_string(name)}\"")
            lines.append(
                f"READONLY Feature_{feature_id}: text = "
                f"\"{escape_string(variable_description)}\""
            )
        lines.extend(["[END_VARIABLES]", ""])

    @classmethod
    def _append_flow_workers(
        cls,
        lines,
        trace_links,
        flows,
        features,
    ) -> None:
        command_number = 1
        scenarios_by_feature = {
            feature["feature_id"]: feature.get("scenarios", [])
            for feature in features
            if feature.get("scenarios", [])
        }
        for flow in flows:
            flow_id = flow.get("flow_id")
            steps = sorted(
                flow.get("flow_steps", []),
                key=lambda step: step.get("position", 0),
            )
            inputs, outputs = cls._collect_business_object_refs(steps)
            lines.append(f"[DEFINE_WORKER: Flow_{flow_id}]")
            cls._append_ref_section(lines, "INPUTS", inputs)
            cls._append_ref_section(lines, "OUTPUTS", outputs)
            command_number = cls._append_flow_steps(
                lines,
                steps,
                command_number,
            )
            cls._append_flow_scenarios(
                lines,
                flow.get("feature_ids", []),
                scenarios_by_feature,
            )
            lines.extend(["[END_WORKER]", ""])
            trace_links.append({
                "spl_ref": f"Flow_{flow_id}",
                "source_kind": "flow",
                "source_id": str(flow_id),
            })

    @staticmethod
    def _collect_business_object_refs(steps) -> tuple[set[str], set[str]]:
        inputs = {
            f"BusinessObject_{object_id}"
            for step in steps
            for object_id in step.get("input_business_object_ids", [])
        }
        outputs = {
            f"BusinessObject_{object_id}"
            for step in steps
            for object_id in step.get("output_business_object_ids", [])
        }
        return inputs, outputs

    @staticmethod
    def _append_ref_section(lines, name, refs) -> None:
        lines.append(f"  [{name}]")
        if refs:
            lines.extend(
                f"    <REF> {ref} </REF>"
                for ref in sorted(refs)
            )
        else:
            lines.append("    # None")
        lines.append(f"  [END_{name}]")

    @classmethod
    def _append_flow_steps(cls, lines, steps, command_number) -> int:
        lines.extend(["  [MAIN_FLOW]", "    [SEQUENTIAL_BLOCK]"])
        for step in steps:
            lines.append(
                f"      COMMAND-{command_number} "
                f"[COMMAND {cls._render_step_body(step)}]"
            )
            command_number += 1
        lines.extend([
            "    [END_SEQUENTIAL_BLOCK]",
            "  [END_MAIN_FLOW]",
        ])
        return command_number

    @staticmethod
    def _render_step_body(step) -> str:
        step_type = step.get("step_type", "systemAction")
        type_prefix = "ActorAction" if step_type == "actorAction" else "SystemAction"
        judgment_suffix = " (judgment)" if step_type == "judgment" else ""
        actors = [f"Actor_{value}" for value in step.get("actor_ids", [])]
        inputs = [
            f"BusinessObject_{value}"
            for value in step.get("input_business_object_ids", [])
        ]
        outputs = [
            f"BusinessObject_{value}"
            for value in step.get("output_business_object_ids", [])
        ]
        actor_part = f"Actor: {', '.join(actors)}. " if actors else ""
        input_part = f"Input: {', '.join(inputs)}. " if inputs else ""
        output_part = f"Output: {', '.join(outputs)}. " if outputs else ""
        return (
            f"{type_prefix}: {escape_string(step.get('step_name', ''))}"
            f"{judgment_suffix} "
            f"({escape_string(step.get('step_description', ''))}). "
            f"{actor_part}{input_part}{output_part}"
        ).strip()

    @staticmethod
    def _append_flow_scenarios(
        lines,
        covered_features,
        scenarios_by_feature,
    ) -> None:
        lines.append("  [SCENARIOS]")
        rendered = False
        for feature_id in covered_features:
            for scenario in scenarios_by_feature.get(feature_id, []):
                lines.extend([
                    "    <EXPECTED-WORKER-BEHAVIOR-GHERKIN>",
                    "    {",
                    f"      Feature: Feature_{feature_id}",
                    f"      Scenario: Scenario_{scenario.get('scenario_id')} "
                    f"\"{escape_string(scenario.get('scenario_name', ''))}\"",
                    f"        # Description: "
                    f"{escape_string(scenario.get('scenario_content', ''))}",
                ])
                criteria = scenario.get("acceptance_criteria", [])
                if criteria:
                    lines.append("        # Acceptance Criteria:")
                    lines.extend(
                        f"        # - "
                        f"{escape_string(criterion.get('criterion_content', ''))}"
                        for criterion in criteria
                    )
                lines.extend([
                    "    }",
                    "    </EXPECTED-WORKER-BEHAVIOR-GHERKIN>",
                ])
                rendered = True
        if not rendered:
            lines.append("    # None")
        lines.append("  [END_SCENARIOS]")
