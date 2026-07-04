from __future__ import annotations

import re
from typing import Any, Dict, List
from .ir import SplSemanticIR, WorkerStepIR, TypeIR


def escape_string(text: Any) -> str:
    if not text:
        return ""
    text = str(text)
    # Clean up non-printable characters (except common ones)
    cleaned = "".join(ch for ch in text if ch.isprintable() or ch in "\n\r\t")
    # Escape quotes
    escaped = cleaned.replace('"', '\\"')
    # Replace newlines with spaces to keep strings single-line in SPL literals
    escaped = escaped.replace('\r\n', ' ').replace('\n', ' ')
    # Collapse multiple spaces
    escaped = re.sub(r'\s+', ' ', escaped)
    return escaped.strip()


class SplSemanticRenderer:
    """
    Renders SplSemanticIR into a formatted SPL document.
    """

    def __init__(self) -> None:
        pass

    def render(self, ir: SplSemanticIR) -> str:
        safe_project_id = re.sub(r'[^a-zA-Z0-9]', '', ir.project_id)[:8]
        if not safe_project_id:
            safe_project_id = "project"

        lines = []
        lines.append(f"[DEFINE_AGENT: Agent_{safe_project_id} \"RequirementSpace SPL semantic export for {escape_string(ir.project_name)}\"]")
        
        # 1. PERSONA
        lines.append("[DEFINE_PERSONA:]")
        lines.append(f"ROLE: {escape_string(ir.persona_role)}")
        lines.append(f"DOMAIN: {escape_string(ir.persona_domain)}")
        lines.append("[END_PERSONA]")
        lines.append("")

        # 2. AUDIENCE
        lines.append("[DEFINE_AUDIENCE:]")
        for actor_id, desc in sorted(ir.audiences.items()):
            lines.append(f"Actor_{actor_id}: \"{escape_string(desc)}\"")
        lines.append("[END_AUDIENCE]")
        lines.append("")

        # 3. CONCEPTS
        lines.append("[DEFINE_CONCEPTS:]")
        for concept_name, concept_desc in sorted(ir.concepts.items()):
            lines.append(f"{concept_name}: \"{escape_string(concept_desc)}\"")
        lines.append("[END_CONCEPTS]")
        lines.append("")

        # 4. CONSTRAINTS
        lines.append("[DEFINE_CONSTRAINTS:]")
        for constraint in ir.constraints:
            lines.append(f"DeliveryScope: \"{escape_string(constraint)}\"")
        lines.append("[END_CONSTRAINTS]")
        lines.append("")

        # 5. TYPES (Include custom Enums first)
        lines.append("[DEFINE_TYPES:]")
        
        # Find all custom enums
        enum_definitions = []
        enum_types_seen = set()
        for t in ir.types.values():
            for f in t.fields:
                if f.enum_candidates and f.spl_type not in enum_types_seen:
                    enum_types_seen.add(f.spl_type)
                    candidates_str = ", ".join(f.enum_candidates)
                    enum_definitions.append(f"{f.spl_type} = [{candidates_str}]")
        
        for enum_def in sorted(enum_definitions):
            lines.append(enum_def)
        if enum_definitions:
            lines.append("")  # Spacer between enums and structs

        # Render structured types
        for t in ir.types.values():
            lines.append(f"\"BusinessObject {t.type_name} (from BO_{t.source_bo_id})\"")
            lines.append(f"{t.type_name} = {{")
            
            field_lines = []
            for f in t.fields:
                desc_part = f"\"Description: {escape_string(f.description)}. Example: {escape_string(f.example)}\" " if f.description or f.example else ""
                field_lines.append(f"  {desc_part}{f.name}: {f.spl_type}")
            
            lines.append(",\n".join(field_lines))
            lines.append("}")
        lines.append("[END_TYPES]")
        lines.append("")

        # 6. VARIABLES
        lines.append("[DEFINE_VARIABLES:]")
        for var_name, var_val in sorted(ir.variables.items()):
            lines.append(f"\"Feature: {escape_string(var_name)}\"")
            lines.append(f"{var_val.get('id_str', 'Feature')}: text = \"{escape_string(var_val.get('desc', ''))}\"")
        lines.append("[END_VARIABLES]")
        lines.append("")

        # 7. WORKERS
        for worker in ir.workers.values():
            lines.append(f"[DEFINE_WORKER: {worker.worker_name}]")
            lines.append(f"  \"Description: {escape_string(worker.description)} (from Flow_{worker.source_flow_id})\"")
            
            # Inputs
            lines.append("  [INPUTS]")
            if worker.inputs:
                for inp in sorted(worker.inputs):
                    lines.append(f"    <REF> {inp} </REF>")
            else:
                lines.append("    # None")
            lines.append("  [END_INPUTS]")
            
            # Outputs
            lines.append("  [OUTPUTS]")
            if worker.outputs:
                for out in sorted(worker.outputs):
                    lines.append(f"    <REF> {out} </REF>")
            else:
                lines.append("    # None")
            lines.append("  [END_OUTPUTS]")
            
            # Main flow with recursive step rendering
            lines.append("  [MAIN_FLOW]")
            
            cmd_counter = 1
            decision_counter = 1

            def render_step_list(steps: List[WorkerStepIR], level: int) -> List[str]:
                nonlocal cmd_counter, decision_counter
                step_lines = []
                indent = "  " * level
                
                # Check if it has a sequential block wrapper
                has_sequential = False
                for step in steps:
                    if step.branch_kind == "sequential":
                        has_sequential = True
                        break
                
                if has_sequential:
                    step_lines.append(f"{indent}[SEQUENTIAL_BLOCK]")
                    level += 1
                    indent = "  " * level

                for step in steps:
                    if step.step_type == "judgment":
                        # Render Decision IF/ELSE block
                        cond = escape_string(step.decision_condition or "condition")
                        step_lines.append(f"{indent}DECISION-{decision_counter} [IF {cond}]")
                        decision_counter += 1
                        
                        # Find positive and negative branches
                        if_steps = [s for s in step.sub_steps if s.branch_kind == "if"]
                        else_steps = [s for s in step.sub_steps if s.branch_kind == "else"]
                        
                        # Render if path
                        step_lines.extend(render_step_list(if_steps, level + 1))
                        
                        # Render else path
                        if else_steps:
                            step_lines.append(f"{indent}[ELSE]")
                            step_lines.extend(render_step_list(else_steps, level + 1))
                            
                        step_lines.append(f"{indent}END_IF")
                    else:
                        # Render normal command step
                        step_lines.append(f"{indent}COMMAND-{cmd_counter} [COMMAND {escape_string(step.command_text)}]")
                        cmd_counter += 1
                
                if has_sequential:
                    level -= 1
                    indent = "  " * level
                    step_lines.append(f"{indent}[END_SEQUENTIAL_BLOCK]")
                    
                return step_lines

            flow_lines = render_step_list(worker.main_flow, 2)
            lines.extend(flow_lines)
            
            lines.append("  [END_MAIN_FLOW]")

            # Scenarios Gherkin
            lines.append("  [SCENARIOS]")
            if worker.scenarios:
                for scen in worker.scenarios:
                    lines.append("    <EXPECTED-WORKER-BEHAVIOR-GHERKIN>")
                    lines.append("    {")
                    lines.append(f"      Feature: Feature_{scen.source_scenario_id}")
                    lines.append(f"      Scenario: \"{escape_string(scen.scenario_name)}\"")
                    for g in scen.given:
                        lines.append(f"        Given {escape_string(g)}")
                    for w in scen.when:
                        lines.append(f"        When {escape_string(w)}")
                    for t in scen.then:
                        lines.append(f"        Then {escape_string(t)}")
                    lines.append("    }")
                    lines.append("    </EXPECTED-WORKER-BEHAVIOR-GHERKIN>")
            else:
                lines.append("    # None")
            lines.append("  [END_SCENARIOS]")

            lines.append("[END_WORKER]")
            lines.append("")

        lines.append("[END_AGENT]")
        return "\n".join(lines) + "\n"
