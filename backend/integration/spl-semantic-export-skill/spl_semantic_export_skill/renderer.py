from __future__ import annotations

import re
from typing import Any

from .ir import SplSemanticIR, WorkerStepIR


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
        lines = [
            f"[DEFINE_AGENT: Agent_{safe_project_id} \"RequirementSpace SPL semantic export for {escape_string(ir.project_name)}\"]"
        ]
        lines.append("[DEFINE_PERSONA:]")
        lines.append(f"ROLE: {escape_string(ir.persona_role)}")
        lines.append(f"DOMAIN: {escape_string(ir.persona_domain)}")
        lines.append("[END_PERSONA]")
        lines.append("")
        self._append_mapping_section(
            lines, "AUDIENCE", ir.audiences,
            lambda key, value: f"Actor_{key}: \"{escape_string(value)}\"",
        )
        self._append_mapping_section(
            lines, "CONCEPTS", ir.concepts,
            lambda key, value: f"{key}: \"{escape_string(value)}\"",
        )
        lines.append("[DEFINE_CONSTRAINTS:]")
        for constraint in ir.constraints:
            if constraint.startswith("BusinessRule_"):
                rule_ref, statement = constraint.split(": ", 1)
                lines.append(f"{rule_ref}: \"{escape_string(statement)}\"")
            else:
                lines.append(f"DeliveryScope: \"{escape_string(constraint)}\"")
        lines.append("[END_CONSTRAINTS]")
        lines.append("")
        self._append_types(lines, ir)
        self._append_variables(lines, ir)
        for worker in ir.workers.values():
            self._append_worker(lines, worker)
        lines.append("[END_AGENT]")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _append_mapping_section(lines, name, values, formatter) -> None:
        lines.append(f"[DEFINE_{name}:]")
        for key, value in sorted(values.items()):
            lines.append(formatter(key, value))
        lines.append(f"[END_{name}]")
        lines.append("")

    @staticmethod
    def _append_types(lines, ir) -> None:
        lines.append("[DEFINE_TYPES:]")
        seen = set()
        enums = []
        for value in ir.types.values():
            for field in value.fields:
                if field.enum_candidates and field.spl_type not in seen:
                    seen.add(field.spl_type)
                    enums.append(f"{field.spl_type} = [{', '.join(field.enum_candidates)}]")
        lines.extend(sorted(enums))
        if enums:
            lines.append("")
        for value in ir.types.values():
            lines.append(f"\"BusinessObject {value.type_name} (from BO_{value.source_bo_id})\"")
            lines.append(f"{value.type_name} = {{")
            fields = []
            for field in value.fields:
                desc = f"\"Description: {escape_string(field.description)}. Example: {escape_string(field.example)}\" " if field.description or field.example else ""
                fields.append(f"  {desc}{field.name}: {field.spl_type}")
            lines.append(",\n".join(fields))
            lines.append("}")
        lines.extend(["[END_TYPES]", ""])

    @staticmethod
    def _append_variables(lines, ir) -> None:
        lines.append("[DEFINE_VARIABLES:]")
        for name, value in sorted(ir.variables.items()):
            lines.append(f"\"Feature: {escape_string(name)}\"")
            lines.append(f"{value.get('id_str', 'Feature')}: text = \"{escape_string(value.get('desc', ''))}\"")
        lines.extend(["[END_VARIABLES]", ""])

    @classmethod
    def _append_worker(cls, lines, worker) -> None:
        lines.append(f"[DEFINE_WORKER: {worker.worker_name}]")
        lines.append(f"  \"Description: {escape_string(worker.description)} (from Flow_{worker.source_flow_id})\"")
        cls._append_refs(lines, "INPUTS", worker.inputs)
        cls._append_refs(lines, "OUTPUTS", worker.outputs)
        lines.append("  [MAIN_FLOW]")
        lines.extend(cls._render_step_list(worker.main_flow, 2, [1, 1]))
        lines.append("  [END_MAIN_FLOW]")
        cls._append_scenarios(lines, worker.scenarios)
        lines.extend(["[END_WORKER]", ""])

    @staticmethod
    def _append_refs(lines, name, refs) -> None:
        lines.append(f"  [{name}]")
        if refs:
            lines.extend(f"    <REF> {ref} </REF>" for ref in sorted(refs))
        else:
            lines.append("    # None")
        lines.append(f"  [END_{name}]")

    @classmethod
    def _render_step_list(cls, steps: list[WorkerStepIR], level: int, counters) -> list[str]:
        result = []
        indent = "  " * level
        sequential = any(step.branch_kind == "sequential" for step in steps)
        if sequential:
            result.append(f"{indent}[SEQUENTIAL_BLOCK]")
            level += 1
            indent = "  " * level
        for step in steps:
            if step.step_type == "judgment":
                result.append(f"{indent}DECISION-{counters[1]} [IF {escape_string(step.decision_condition or 'condition')}]")
                counters[1] += 1
                result.extend(cls._render_step_list(
                    [sub for sub in step.sub_steps if sub.branch_kind == "if"],
                    level + 1, counters,
                ))
                else_steps = [sub for sub in step.sub_steps if sub.branch_kind == "else"]
                if else_steps:
                    result.append(f"{indent}[ELSE]")
                    result.extend(cls._render_step_list(else_steps, level + 1, counters))
                result.append(f"{indent}END_IF")
            else:
                result.append(f"{indent}COMMAND-{counters[0]} [COMMAND {escape_string(step.command_text)}]")
                counters[0] += 1
        if sequential:
            result.append(f"{'  ' * (level - 1)}[END_SEQUENTIAL_BLOCK]")
        return result

    @staticmethod
    def _append_scenarios(lines, scenarios) -> None:
        lines.append("  [SCENARIOS]")
        if not scenarios:
            lines.append("    # None")
        for scenario in scenarios:
            lines.extend([
                "    <EXPECTED-WORKER-BEHAVIOR-GHERKIN>",
                "    {",
                f"      Feature: Feature_{scenario.source_scenario_id}",
                f"      Scenario: \"{escape_string(scenario.scenario_name)}\"",
            ])
            lines.extend(f"        Given {escape_string(value)}" for value in scenario.given)
            lines.extend(f"        When {escape_string(value)}" for value in scenario.when)
            lines.extend(f"        Then {escape_string(value)}" for value in scenario.then)
            lines.extend(["    }", "    </EXPECTED-WORKER-BEHAVIOR-GHERKIN>"])
        lines.append("  [END_SCENARIOS]")
