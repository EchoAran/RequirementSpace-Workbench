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

        # Start constructing SPL lines
        lines = []
        lines.append(f"[DEFINE_AGENT: Agent_{safe_project_id} \"RequirementSpace SPL syntax export for {escape_string(project_name)}\"]")
        
        # 1. PERSONA
        lines.append("[DEFINE_PERSONA:]")
        lines.append(f"ROLE: Requirement specification agent for the exported requirement space {escape_string(project_name)}.")
        lines.append(f"DOMAIN: {escape_string(project_name)}")
        lines.append("[END_PERSONA]")
        lines.append("")

        # 2. AUDIENCE (Actors)
        actors = payload.get("actors", [])
        if not actors:
            warnings.append({
                "code": "empty_actors",
                "message": "Project has no actors defined.",
                "source": {"kind": "project", "id": project_id}
            })
        lines.append("[DEFINE_AUDIENCE:]")
        for actor in actors:
            actor_id = actor.get("actor_id")
            actor_name = actor.get("actor_name", "")
            actor_desc = actor.get("actor_description", "")
            lines.append(f"Actor_{actor_id}: \"{escape_string(actor_name)}: {escape_string(actor_desc)}\"")
        lines.append("[END_AUDIENCE]")
        lines.append("")

        # 3. CONCEPTS (Project Description & Original requirements)
        lines.append("[DEFINE_CONCEPTS:]")
        lines.append(f"ProjectDescription: \"{escape_string(project_desc)}\"")
        lines.append(f"UserRequirements: \"{escape_string(user_reqs)}\"")
        lines.append("[END_CONCEPTS]")
        lines.append("")

        # 4. CONSTRAINTS (Delivery Scopes and Unresolved Gates)
        features = payload.get("features", [])
        unresolved_gates = payload.get("unresolved_gates", [])
        
        lines.append("[DEFINE_CONSTRAINTS:]")
        
        # Delivery Scope constraints
        for feat in features:
            feat_id = feat.get("feature_id")
            feat_name = feat.get("feature_name", "")
            scope_obj = feat.get("scope") or {}
            scope_status = scope_obj.get("scope_status")
            scope_reason = scope_obj.get("reason", "")
            
            # Check if leaf feature lacks scope
            children_ids = feat.get("children_ids", [])
            is_leaf = not children_ids
            
            if not scope_status:
                scope_status = "current"
                if is_leaf:
                    warnings.append({
                        "code": "missing_scope",
                        "message": f"Leaf feature Feature_{feat_id} '{feat_name}' is missing scope status.",
                        "source": {"kind": "feature", "id": str(feat_id)}
                    })
            
            # Map scope_status to localized or standard string
            status_map = {
                "current": "current" if is_english else "current (本期)",
                "postponed": "postponed" if is_english else "postponed (暂缓)",
                "exclude": "excluded" if is_english else "exclude (不纳入)",
            }
            status_str = status_map.get(scope_status, scope_status)
            reason_str = f" Reason: {escape_string(scope_reason)}" if scope_reason else ""
            lines.append(f"DeliveryScope: \"Feature_{feat_id} {escape_string(feat_name)} is {status_str}.{reason_str}\"")
        
        # Unresolved Gates constraints
        for gate in unresolved_gates:
            gate_code = gate.get("code") or gate.get("finding_id", "gate")
            gate_desc = gate.get("description", "")
            gate_detail = "" if is_english else f": {escape_string(gate_desc)}"
            lines.append(f"ExportGate: \"Unresolved gate {escape_string(gate_code)}{gate_detail}\"")
            warnings.append({
                "code": "unresolved_gate",
                "message": f"Export includes unresolved gate: {gate_code}.",
                "source": {"kind": "project", "id": project_id}
            })
            
        lines.append("[END_CONSTRAINTS]")
        lines.append("")

        # 5. TYPES (Business Objects)
        business_objects = payload.get("business_objects", [])
        if not business_objects:
            warnings.append({
                "code": "empty_business_objects",
                "message": "Project has no business objects defined.",
                "source": {"kind": "project", "id": project_id}
            })

        lines.append("[DEFINE_TYPES:]")
        for bo in business_objects:
            bo_id = bo.get("business_object_id")
            bo_name = bo.get("business_object_name", "")
            bo_desc = bo.get("business_object_description", "")
            
            lines.append(f"\"BusinessObject {escape_string(bo_name)}: {escape_string(bo_desc)}\"")
            lines.append(f"BusinessObject_{bo_id} = {{")
            
            attrs = bo.get("business_object_attributes", [])
            attr_lines = []
            for attr in attrs:
                attr_name = attr.get("business_object_attribute_name", "")
                attr_desc = attr.get("business_object_attribute_description", "")
                attr_type = attr.get("business_object_attribute_type", "string").lower()
                attr_example = attr.get("business_object_attribute_example", "")
                
                # Clean elements names to be alphanumeric/underscore
                safe_attr_name = re.sub(r'[^a-zA-Z0-9_]', '', attr_name)
                if not safe_attr_name:
                    safe_attr_name = f"field_{attr.get('business_object_attribute_id')}"
                
                # Type mapping
                spl_type = "text"
                if attr_type in ("string", "text", "datetime"):
                    spl_type = "text"
                elif attr_type in ("integer", "int", "number", "float"):
                    spl_type = "number"
                elif attr_type in ("bool", "boolean"):
                    spl_type = "boolean"
                elif attr_type == "array[string]":
                    spl_type = "List [text]"
                elif attr_type == "array[number]":
                    spl_type = "List [number]"
                else:
                    spl_type = "text"
                    warnings.append({
                        "code": "unsupported_type",
                        "message": f"Unsupported attribute type '{attr_type}' mapped to 'text'.",
                        "source": {"kind": "business_object", "id": str(bo_id)}
                    })
                
                desc_comment = f"\"Description: {escape_string(attr_desc)}. Example: {escape_string(attr_example)}\" " if attr_desc or attr_example else ""
                attr_lines.append(f"  {desc_comment}{safe_attr_name}: {spl_type}")
            
            # Print comma-separated elements
            lines.append(",\n".join(attr_lines))
            lines.append("}")
        lines.append("[END_TYPES]")
        lines.append("")

        # 6. VARIABLES (Features catalog)
        if not features:
            warnings.append({
                "code": "empty_features",
                "message": "Project has no features defined.",
                "source": {"kind": "project", "id": project_id}
            })
            
        lines.append("[DEFINE_VARIABLES:]")
        for feat in features:
            feat_id = feat.get("feature_id")
            feat_name = feat.get("feature_name", "")
            feat_desc = feat.get("feature_description", "")
            scope_obj = feat.get("scope") or {}
            scope_status = scope_obj.get("scope_status") or "current"
            parent_id = feat.get("parent_id")
            children_ids = feat.get("children_ids", [])
            
            parent_str = f"Feature_{parent_id}" if parent_id else "None"
            children_str = ", ".join(f"Feature_{c}" for c in children_ids) if children_ids else "None"
            
            var_desc = f"Description: {escape_string(feat_desc)}. Scope: {scope_status}. Parent: {parent_str}. Children: [{children_str}]."
            lines.append(f"\"Feature: {escape_string(feat_name)}\"")
            lines.append(f"READONLY Feature_{feat_id}: text = \"{escape_string(var_desc)}\"")
        lines.append("[END_VARIABLES]")
        lines.append("")

        # 7. WORKERS (Flows)
        flows = payload.get("flows", [])
        if not flows:
            warnings.append({
                "code": "empty_flows",
                "message": "Project has no flows defined.",
                "source": {"kind": "project", "id": project_id}
            })
            
        cmd_counter = 1
        
        # Build scenarios lookup by feature id
        scenarios_by_feature: Dict[int, List[Dict[str, Any]]] = {}
        for feat in features:
            scenarios = feat.get("scenarios", [])
            if scenarios:
                scenarios_by_feature[feat["feature_id"]] = scenarios

        for flow in flows:
            flow_id = flow.get("flow_id")
            flow_name = flow.get("flow_name", "")
            flow_desc = flow.get("flow_description", "")
            covered_features = flow.get("feature_ids", [])
            
            lines.append(f"[DEFINE_WORKER: Flow_{flow_id}]")
            
            # Simple Inputs / Outputs declaration
            # Collect input and output objects across steps
            input_bos = set()
            output_bos = set()
            steps = flow.get("flow_steps", [])
            
            # Sort steps by position
            sorted_steps = sorted(steps, key=lambda s: s.get("position", 0))
            for step in sorted_steps:
                for bo_in in step.get("input_business_object_ids", []):
                    input_bos.add(f"BusinessObject_{bo_in}")
                for bo_out in step.get("output_business_object_ids", []):
                    output_bos.add(f"BusinessObject_{bo_out}")
            
            # Render inputs
            lines.append("  [INPUTS]")
            if input_bos:
                for bo_name in sorted(list(input_bos)):
                    lines.append(f"    <REF> {bo_name} </REF>")
            else:
                lines.append("    # None")
            lines.append("  [END_INPUTS]")
            
            # Render outputs
            lines.append("  [OUTPUTS]")
            if output_bos:
                for bo_name in sorted(list(output_bos)):
                    lines.append(f"    <REF> {bo_name} </REF>")
            else:
                lines.append("    # None")
            lines.append("  [END_OUTPUTS]")
            
            # Render flows
            lines.append("  [MAIN_FLOW]")
            lines.append("    [SEQUENTIAL_BLOCK]")
            
            for step in sorted_steps:
                step_name = step.get("step_name", "")
                step_desc = step.get("step_description", "")
                step_type = step.get("step_type", "systemAction")
                
                step_actors = [f"Actor_{a}" for a in step.get("actor_ids", [])]
                step_inputs = [f"BusinessObject_{bi}" for bi in step.get("input_business_object_ids", [])]
                step_outputs = [f"BusinessObject_{bo}" for bo in step.get("output_business_object_ids", [])]
                
                actor_part = f"Actor: {', '.join(step_actors)}. " if step_actors else ""
                input_part = f"Input: {', '.join(step_inputs)}. " if step_inputs else ""
                output_part = f"Output: {', '.join(step_outputs)}. " if step_outputs else ""
                
                # Prefix type
                type_prefix = "SystemAction"
                judgment_suffix = ""
                if step_type == "actorAction":
                    type_prefix = "ActorAction"
                elif step_type == "judgment":
                    type_prefix = "SystemAction"
                    judgment_suffix = " (judgment)"
                
                step_body = f"{type_prefix}: {escape_string(step_name)}{judgment_suffix} ({escape_string(step_desc)}). {actor_part}{input_part}{output_part}"
                lines.append(f"      COMMAND-{cmd_counter} [COMMAND {step_body.strip()}]")
                cmd_counter += 1
                
            lines.append("    [END_SEQUENTIAL_BLOCK]")
            lines.append("  [END_MAIN_FLOW]")
            
            # Render scenarios associated with the flow
            lines.append("  [SCENARIOS]")
            scenarios_rendered = False
            for feat_id in covered_features:
                scenarios = scenarios_by_feature.get(feat_id, [])
                for scen in scenarios:
                    scen_id = scen.get("scenario_id")
                    scen_name = scen.get("scenario_name", "")
                    scen_content = scen.get("scenario_content", "")
                    criteria = scen.get("acceptance_criteria", [])
                    
                    lines.append("    <EXPECTED-WORKER-BEHAVIOR-GHERKIN>")
                    lines.append("    {")
                    lines.append(f"      Feature: Feature_{feat_id}")
                    lines.append(f"      Scenario: Scenario_{scen_id} \"{escape_string(scen_name)}\"")
                    lines.append(f"        # Description: {escape_string(scen_content)}")
                    if criteria:
                        lines.append("        # Acceptance Criteria:")
                        for ac in criteria:
                            lines.append(f"        # - {escape_string(ac.get('criterion_content', ''))}")
                    lines.append("    }")
                    lines.append("    </EXPECTED-WORKER-BEHAVIOR-GHERKIN>")
                    scenarios_rendered = True
            if not scenarios_rendered:
                lines.append("    # None")
            lines.append("  [END_SCENARIOS]")
            
            lines.append(f"[END_WORKER]")
            lines.append("")
            
            trace_links.append({
                "spl_ref": f"Flow_{flow_id}",
                "source_kind": "flow",
                "source_id": str(flow_id)
            })

        lines.append("[END_AGENT]")
        spl_text = "\n".join(lines) + "\n"

        return spl_text, warnings, trace_links
