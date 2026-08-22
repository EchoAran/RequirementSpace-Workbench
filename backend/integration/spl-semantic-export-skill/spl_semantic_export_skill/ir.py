from __future__ import annotations

from typing import Any


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set)):
        return list(value)
    return [value]


class WarningSourceIR:
    def __init__(self, kind: str, id: str) -> None:
        self.kind = kind
        self.id = id

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "id": self.id}


class SplExportWarningIR:
    def __init__(self, code: str, message: str, source: WarningSourceIR | None = None) -> None:
        self.code = code
        self.message = message
        self.source = source

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "source": self.source.to_dict() if self.source else None
        }


class TraceLinkIR:
    def __init__(self, spl_ref: str, source_kind: str, source_id: str) -> None:
        self.spl_ref = spl_ref
        self.source_kind = source_kind
        self.source_id = source_id

    def to_dict(self) -> dict[str, str]:
        return {
            "spl_ref": self.spl_ref,
            "source_kind": self.source_kind,
            "source_id": self.source_id
        }


class WorkerStepIR:
    def __init__(
        self,
        source_step_id: int | None = None,
        step_type: str = "systemAction",
        command_text: str = "",
        input_refs: list[str] | None = None,
        output_refs: list[str] | None = None,
        decision_condition: str | None = None,
        branch_kind: str | None = None,  # "if" | "else" | "elseif" | "sequential"
        sub_steps: list[WorkerStepIR] | None = None
    ) -> None:
        self.source_step_id = source_step_id
        self.step_type = _as_text(step_type)
        self.command_text = _as_text(command_text)
        self.input_refs = [_as_text(v) for v in _as_list(input_refs)]
        self.output_refs = [_as_text(v) for v in _as_list(output_refs)]
        self.decision_condition = _as_text(decision_condition) if decision_condition is not None else None
        self.branch_kind = branch_kind
        self.sub_steps = [v for v in _as_list(sub_steps) if isinstance(v, WorkerStepIR)]


class ScenarioIR:
    def __init__(
        self,
        source_scenario_id: int,
        source_acceptance_criterion_ids: list[int],
        worker_id: int | None = None,
        flow_type: str = "normal",  # "normal" | "alternative" | "exception"
        scenario_name: str = "",
        given: list[str] | None = None,
        when: list[str] | None = None,
        then: list[str] | None = None
    ) -> None:
        self.source_scenario_id = source_scenario_id
        self.source_acceptance_criterion_ids = _as_list(source_acceptance_criterion_ids)
        self.worker_id = worker_id
        self.flow_type = _as_text(flow_type)
        self.scenario_name = _as_text(scenario_name)
        self.given = [_as_text(v) for v in _as_list(given)]
        self.when = [_as_text(v) for v in _as_list(when)]
        self.then = [_as_text(v) for v in _as_list(then)]


class WorkerIR:
    def __init__(
        self,
        worker_id: int,
        worker_name: str,
        description: str,
        source_flow_id: int,
        covered_feature_ids: list[int] | None = None,
        actors: list[str] | None = None,
        inputs: list[str] | None = None,
        outputs: list[str] | None = None,
        main_flow: list[WorkerStepIR] | None = None,
        alternative_flows: list[dict[str, Any]] | None = None,
        exception_flows: list[dict[str, Any]] | None = None,
        scenarios: list[ScenarioIR] | None = None,
        confidence: float = 1.0
    ) -> None:
        self.worker_id = worker_id
        self.worker_name = _as_text(worker_name)
        self.description = _as_text(description)
        self.source_flow_id = source_flow_id
        self.covered_feature_ids = _as_list(covered_feature_ids)
        self.actors = [_as_text(v) for v in _as_list(actors)]
        self.inputs = [_as_text(v) for v in _as_list(inputs)]
        self.outputs = [_as_text(v) for v in _as_list(outputs)]
        self.main_flow = [v for v in _as_list(main_flow) if isinstance(v, WorkerStepIR)]
        self.alternative_flows = [v for v in _as_list(alternative_flows) if isinstance(v, dict)]
        self.exception_flows = [v for v in _as_list(exception_flows) if isinstance(v, dict)]
        self.scenarios = [v for v in _as_list(scenarios) if isinstance(v, ScenarioIR)]
        self.confidence = confidence


class TypeFieldIR:
    def __init__(
        self,
        name: str,
        spl_type: str,
        description: str = "",
        example: str = "",
        enum_candidates: list[str] | None = None
    ) -> None:
        self.name = _as_text(name)
        self.spl_type = _as_text(spl_type)
        self.description = _as_text(description)
        self.example = _as_text(example)
        self.enum_candidates = [_as_text(v) for v in _as_list(enum_candidates)]


class TypeIR:
    def __init__(self, type_name: str, source_bo_id: int, fields: list[TypeFieldIR] | None = None) -> None:
        self.type_name = type_name
        self.source_bo_id = source_bo_id
        self.fields = fields or []


class SplSemanticIR:
    def __init__(self, raw_payload: dict[str, Any]) -> None:
        self.raw = raw_payload
        self.project_id = raw_payload.get("project", {}).get("project_id", "00000000")
        self.project_name = raw_payload.get("project", {}).get("project_name", "Unknown")
        self.project_desc = raw_payload.get("project", {}).get("project_description", "")
        self.user_reqs = raw_payload.get("project", {}).get("user_requirements", "")

        self.persona_role = f"Requirement specification agent for the exported requirement space {self.project_name}."
        self.persona_domain = self.project_name
        self.audiences: dict[str, str] = {}  # actor_id_str -> "ActorName: ActorDesc"
        self.concepts: dict[str, str] = {}
        self.constraints: list[str] = []
        self.types: dict[str, TypeIR] = {}  # bo_id_str -> TypeIR
        self.variables: dict[str, Any] = {}
        self.workers: dict[str, WorkerIR] = {}  # flow_id_str -> WorkerIR
        self.trace_links: list[TraceLinkIR] = []
        self.warnings: list[SplExportWarningIR] = []
        self.bo_id_to_type_name: dict[str, str] = {}  # Maps bo_id_str -> normalized type_name for reference matching
        self.semantic_identifier_map: dict[str, str] = {}  # e.g., "business_object:20" -> "DeviceArchive"
        self.unbound_scenarios: list[ScenarioIR] = []
