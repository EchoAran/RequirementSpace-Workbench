from __future__ import annotations

import asyncio
import logging
import os
import re
from collections.abc import Callable
from contextvars import copy_context
from typing import Any

from .ir import (
    ScenarioIR,
    SplExportWarningIR,
    SplSemanticIR,
    TraceLinkIR,
    TypeFieldIR,
    TypeIR,
    WarningSourceIR,
    WorkerIR,
    WorkerStepIR,
)
from .prompts import AC_TO_SCENARIO_PROMPT, COVERAGE_REVIEW_PROMPT, FLOW_TO_WORKER_PROMPT, TYPE_NORMALIZATION_PROMPT
from .renderer import SplSemanticRenderer
from .schema import SplExportInputDict, SplExportOutputDict
from .validators import SplSemanticValidator

logger = logging.getLogger(__name__)


def _output_language(payload: SplExportInputDict) -> str:
    return payload.get("export_options", {}).get("language") or "zh-CN"


def _localized(payload: SplExportInputDict, zh_cn: str, en_us: str) -> str:
    return en_us if _output_language(payload) == "en-US" else zh_cn


def run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import threading
        from concurrent.futures import Future

        fut = Future()

        def run_in_thread():
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                result = new_loop.run_until_complete(coro)
                fut.set_result(result)
            except Exception as e:
                fut.set_exception(e)
            finally:
                new_loop.close()

        context = copy_context()
        t = threading.Thread(target=lambda: context.run(run_in_thread))
        t.start()
        return fut.result()
    else:
        return asyncio.run(coro)


class SplSemanticExportSkill:
    """
    Skill to perform LLM-backed semantic compiler export of RequirementSpace models to SPL.
    Coordinates type normalization, worker mapping, Gherkin extraction, and coverage review.
    """

    def __init__(self, ask_json: Callable[[str], dict[str, Any]] | None = None) -> None:
        self._ask_json = ask_json
        self._renderer = SplSemanticRenderer()
        self._validator = SplSemanticValidator()

    def export(self, payload: SplExportInputDict) -> SplExportOutputDict:
        ir = SplSemanticIR(payload)

        if not self._ask_json:
            raise ValueError("spl_semantic_llm_unavailable")

        run_async(self._export_async(payload, ir))
        val_report = self._validator.validate(ir)
        run_async(self._run_llm_coverage_review_async(payload, ir, val_report))
        spl_text = self._renderer.render(ir)
        has_major_warnings = any(
            w.code in (
                "missing_type_ref",
                "unmapped_flow",
                "uncovered_feature",
                "judgment_branch_unresolved",
                "duplicate_semantic_identifier",
                "uncovered_acceptance_criterion"
            )
            for w in ir.warnings
        )
        quality = "semantic_with_warnings" if (has_major_warnings or not val_report.get("coverage_passed", False)) else "semantic_verified"
        return {
            "spl_text": spl_text,
            "quality": quality,
            "warnings": [w.to_dict() for w in ir.warnings],
            "trace_links": [t.to_dict() for t in ir.trace_links],
            "coverage_report": val_report
        }

    async def _export_async(self, payload: SplExportInputDict, ir: SplSemanticIR) -> None:
        # Read concurrency limit from environment variables (default 5)
        concurrency_limit = 5
        for env_name in ("SPL_SEMANTIC_AC_MAX_CONCURRENCY", "SPL_SEMANTIC_FLOW_MAX_CONCURRENCY", "SPL_SEMANTIC_TYPE_MAX_CONCURRENCY"):
            val = os.getenv(env_name)
            if val:
                try:
                    concurrency_limit = int(val)
                    break
                except ValueError:
                    pass
        else:
            try:
                concurrency_limit = int(os.getenv("SPL_SEMANTIC_MAX_CONCURRENCY", "5"))
            except ValueError:
                concurrency_limit = 5

        sem = asyncio.Semaphore(concurrency_limit)

        async def ask_with_sem_and_timeout(prompt: str) -> dict:
            async with sem:
                return await asyncio.wait_for(
                    asyncio.to_thread(self._ask_json, prompt),
                    timeout=25.0  # 25 seconds timeout per LLM request
                )

        # Stage 1: Parallel Type Normalization (needs to complete first to provide mappings to Stage 2)
        business_objects = payload.get("business_objects", [])
        if business_objects:
            await asyncio.gather(*(
                self._normalize_single_bo(bo, ir, ask_with_sem_and_timeout)
                for bo in business_objects
            ))

        # Stage 2 & 3: Run Flow to Worker conversion and AC Scenario extraction concurrently
        await asyncio.gather(
            self._convert_flows_async(payload, ir, ask_with_sem_and_timeout),
            self._extract_scenarios_async(payload, ir, ask_with_sem_and_timeout)
        )

        # Bind scenarios to workers synchronously after both parallel tasks complete
        self._bind_scenarios_to_workers(payload, ir)

    async def _normalize_single_bo(self, bo: dict, ir: SplSemanticIR, ask_fn: Callable[[str], Any]) -> None:
        bo_id = bo.get("business_object_id")
        bo_name = bo.get("business_object_name", "")
        bo_desc = bo.get("business_object_description", "")

        # Format attributes list for the prompt
        attrs_str = []
        for attr in bo.get("business_object_attributes", []):
            attrs_str.append(
                f"- {attr.get('business_object_attribute_name')}: "
                f"type={attr.get('business_object_attribute_type')}, "
                f"desc={attr.get('business_object_attribute_description')}, "
                f"example={attr.get('business_object_attribute_example')}"
            )

        prompt = TYPE_NORMALIZATION_PROMPT.format(
            bo_name=bo_name,
            bo_description=bo_desc,
            bo_attributes="\n".join(attrs_str),
            output_language=_output_language(ir.raw),
        )

        res = await ask_fn(prompt)
        if not isinstance(res, dict) or not res.get("type_name") or not isinstance(res.get("fields"), list):
            raise ValueError("spl_semantic_invalid_type_output")
        type_name = re.sub(r'[^a-zA-Z0-9]', '', res["type_name"])
        if not type_name:
            raise ValueError("spl_semantic_invalid_type_identifier")

        fields_ir = []
        for field in res["fields"]:
            field_name = re.sub(r'[^a-zA-Z0-9_]', '', field.get("normalized_name", ""))
            if not field_name or not field.get("spl_type"):
                raise ValueError("spl_semantic_invalid_type_field")
            fields_ir.append(TypeFieldIR(
                name=field_name,
                spl_type=field["spl_type"],
                description=field.get("description", ""),
                example=field.get("example", ""),
                enum_candidates=field.get("enum_candidates", []) if field.get("is_enum") else []
            ))

        type_ir = TypeIR(type_name=type_name, source_bo_id=bo_id, fields=fields_ir)
        ir.types[str(bo_id)] = type_ir
        ir.bo_id_to_type_name[str(bo_id)] = type_name
        ir.semantic_identifier_map[f"business_object:{bo_id}"] = type_name
        ir.trace_links.append(TraceLinkIR(spl_ref=type_name, source_kind="business_object", source_id=str(bo_id)))

    async def _convert_flows_async(self, payload: SplExportInputDict, ir: SplSemanticIR, ask_fn: Callable[[str], Any]) -> None:
        actors_mapping = {}
        for actor in payload.get("actors", []):
            actor_id = actor.get("actor_id")
            actor_name = actor.get("actor_name", "")
            actors_mapping[f"Actor_{actor_id}"] = actor_name
            ir.audiences[str(actor_id)] = f"{actor_name}: {actor.get('actor_description')}"
            ir.semantic_identifier_map[f"actor:{actor_id}"] = f"Actor_{actor_id}"

        ir.concepts["ProjectDescription"] = ir.project_desc
        ir.concepts["UserRequirements"] = ir.user_reqs
        self._register_domain_rules(payload, ir)

        # Map Constraints (Scope statuses)
        for feat in payload.get("features", []):
            feat_id = feat.get("feature_id")
            feat_name = feat.get("feature_name", "")
            scope_obj = feat.get("scope") or {}
            scope_status = scope_obj.get("scope_status") or "current"
            scope_reason = scope_obj.get("reason", "")

            reason_str = f" Reason: {scope_reason}" if scope_reason else ""
            ir.constraints.append(f"Feature_{feat_id} {feat_name} is {scope_status}.{reason_str}")

            ir.variables[feat_name] = {
                "id_str": f"Feature_{feat_id}",
                "desc": f"Scope: {scope_status}. Parent: Feature_{feat.get('parent_id') or 'None'}."
            }

        # Convert flows concurrently
        flows = payload.get("flows", [])
        if flows:
            await asyncio.gather(*(
                self._convert_single_flow(flow, actors_mapping, ir, ask_fn)
                for flow in flows
            ))

    async def _convert_single_flow(self, flow: dict, actors_mapping: dict, ir: SplSemanticIR, ask_fn: Callable[[str], Any]) -> None:
        flow_id = flow.get("flow_id")
        flow_desc = flow.get("flow_description", "")
        covered_features = flow.get("feature_ids", [])
        prompt = self._build_flow_worker_prompt(flow, actors_mapping, ir)

        res = await ask_fn(prompt)
        worker = self._build_worker_from_response(
            flow_id,
            flow_desc,
            covered_features,
            res,
        )
        self._register_flow_worker(ir, flow_id, worker)
        self._register_flow_transition_traces(flow, ir)

    @staticmethod
    def _build_flow_worker_prompt(flow: dict, actors_mapping: dict, ir: SplSemanticIR) -> str:
        steps = []
        for step in sorted(flow.get("flow_steps", []), key=lambda s: s.get("position", 0)):
            actor_names = [actors_mapping.get(f"Actor_{a}", "Unknown") for a in step.get("actor_ids", [])]
            input_names = [ir.bo_id_to_type_name.get(str(value), "Unknown") for value in step.get("input_business_object_ids", [])]
            output_names = [ir.bo_id_to_type_name.get(str(value), "Unknown") for value in step.get("output_business_object_ids", [])]
            steps.append(
                f"Step {step.get('position')}: {step.get('step_name')} (desc: {step.get('step_description')}, "
                f"type: {step.get('step_type')}, actors: {actor_names}, inputs: {input_names}, outputs: {output_names})"
            )
        transitions = []
        if len(flow.get("flow_steps", [])) > 1 and not flow.get("transitions", []):
            raise ValueError("spl_export_flow_transitions_missing")
        outgoing_counts: dict[int, int] = {}
        for transition in flow.get("transitions", []):
            source_id = transition.get("source_step_id")
            outgoing_counts[source_id] = outgoing_counts.get(source_id, 0) + 1
        for transition in sorted(
            flow.get("transitions", []),
            key=lambda value: (
                value.get("source_step_id"),
                value.get("position", 0),
                value.get("target_step_id"),
            ),
        ):
            label = transition.get("label", "")
            condition = transition.get("condition_text", "")
            is_default = bool(transition.get("is_default"))
            if outgoing_counts.get(transition.get("source_step_id"), 0) > 1 and not (
                label or condition or is_default
            ):
                raise ValueError(
                    "spl_export_transition_semantics_missing:"
                    f"{transition.get('transition_id')}"
                )
            transitions.append(
                f"Transition {transition.get('transition_id')}: "
                f"{transition.get('source_step_id')} -> {transition.get('target_step_id')}; "
                f"label={label}; condition={condition}; default={is_default}; "
                f"tags={transition.get('semantic_tags', [])}"
            )
        target_uuids = {
            value
            for value in [flow.get("logical_uuid")]
            if value
        }
        target_uuids.update(
            step.get("logical_uuid")
            for step in flow.get("flow_steps", [])
            if step.get("logical_uuid")
        )
        target_uuids.update(
            transition.get("logical_uuid")
            for transition in flow.get("transitions", [])
            if transition.get("logical_uuid")
        )
        linked_rule_ids = {
            link.get("rule_id")
            for link in ir.raw.get("rule_links", [])
            if link.get("link_purpose") == "applies_to"
            and link.get("target_logical_uuid") in target_uuids
        }
        flow_rules = [
            f"BusinessRule_{rule.get('rule_id') or rule.get('id')}: {rule.get('statement')}"
            for rule in ir.raw.get("domain_rules", [])
            if (rule.get("rule_id") or rule.get("id")) in linked_rule_ids
        ]
        return FLOW_TO_WORKER_PROMPT.format(
            flow_name=flow.get("flow_name", ""),
            flow_description=flow.get("flow_description", ""),
            flow_steps="\n".join(steps),
            flow_transitions="\n".join(transitions),
            flow_rules="\n".join(flow_rules),
            types_mapping=ir.bo_id_to_type_name,
            actors_mapping=actors_mapping,
            output_language=_output_language(ir.raw),
        )

    @staticmethod
    def _register_domain_rules(payload: SplExportInputDict, ir: SplSemanticIR) -> None:
        rules = payload.get("domain_rules", [])
        links = payload.get("rule_links", [])
        for rule in rules:
            rule_id = rule.get("rule_id") or rule.get("id")
            statement = rule.get("statement")
            if rule_id is None or not statement:
                raise ValueError("spl_export_invalid_domain_rule")
            ir.constraints.append(f"BusinessRule_{rule_id}: {statement}")
            ir.trace_links.append(TraceLinkIR(
                spl_ref=f"BusinessRule_{rule_id}",
                source_kind="domain_rule",
                source_id=str(rule_id),
            ))
        for link in links:
            purpose = link.get("link_purpose")
            target_kind = link.get("target_kind")
            target_uuid = link.get("target_logical_uuid")
            if purpose not in {"source", "applies_to"} or not target_kind or not target_uuid:
                raise ValueError("spl_export_invalid_rule_link")
            ir.trace_links.append(TraceLinkIR(
                spl_ref=(
                    f"BusinessRule_{link.get('rule_id')}->"
                    f"{target_kind}:{target_uuid}"
                ),
                source_kind="rule_link",
                source_id=str(link.get("logical_uuid") or link.get("id")),
            ))

    @staticmethod
    def _register_flow_transition_traces(flow: dict, ir: SplSemanticIR) -> None:
        for transition in flow.get("transitions", []):
            transition_id = transition.get("transition_id")
            ir.trace_links.append(TraceLinkIR(
                spl_ref=f"FlowTransition_{transition_id}",
                source_kind="flow_transition",
                source_id=str(transition.get("logical_uuid") or transition_id),
            ))

    @staticmethod
    def _parse_worker_step(step: dict) -> WorkerStepIR:
        return WorkerStepIR(
            source_step_id=step.get("source_step_id"),
            step_type=step.get("step_type", "systemAction"),
            command_text=step.get("command_text", ""),
            input_refs=step.get("input_refs", []),
            output_refs=step.get("output_refs", []),
            decision_condition=step.get("decision_condition"),
            branch_kind=step.get("branch_kind", "sequential"),
            sub_steps=[
                SplSemanticExportSkill._parse_worker_step(sub)
                for sub in step.get("sub_steps", [])
            ],
        )

    @classmethod
    def _build_worker_from_response(cls, flow_id, flow_desc, covered_features, response) -> WorkerIR:
        if not isinstance(response, dict) or not response.get("worker_name"):
            raise ValueError("spl_semantic_invalid_worker_output")
        if not isinstance(response.get("main_flow_steps"), list):
            raise ValueError("spl_semantic_invalid_worker_steps")
        worker_name = re.sub(
            r"[^a-zA-Z0-9]",
            "",
            response["worker_name"],
        )
        if not worker_name:
            raise ValueError("spl_semantic_invalid_worker_identifier")
        return WorkerIR(
            worker_id=flow_id,
            worker_name=worker_name,
            description=response.get("description", flow_desc),
            source_flow_id=flow_id,
            covered_feature_ids=covered_features,
            actors=response.get("actors", []),
            inputs=response.get("inputs", []),
            outputs=response.get("outputs", []),
            main_flow=[
                cls._parse_worker_step(step)
                for step in response.get("main_flow_steps", [])
            ],
        )

    @staticmethod
    def _register_flow_worker(ir, flow_id, worker) -> None:
        ir.workers[str(flow_id)] = worker
        ir.semantic_identifier_map[f"flow:{flow_id}"] = worker.worker_name
        ir.trace_links.append(TraceLinkIR(
            spl_ref=worker.worker_name,
            source_kind="flow",
            source_id=str(flow_id),
        ))

    async def _extract_scenarios_async(self, payload: SplExportInputDict, ir: SplSemanticIR, ask_fn: Callable[[str], Any]) -> None:
        features = payload.get("features", [])

        # Parallel scenarios extraction for all features
        results = await asyncio.gather(*(
            self._extract_single_feature_scenarios(
                feat,
                ask_fn,
                _output_language(payload),
            )
            for feat in features
        ))

        all_scenarios: list[ScenarioIR] = []
        for res_list in results:
            if res_list:
                all_scenarios.extend(res_list)

        ir.unbound_scenarios = all_scenarios

    def _bind_scenarios_to_workers(self, payload: SplExportInputDict, ir: SplSemanticIR) -> None:
        for scen in ir.unbound_scenarios:
            for worker in ir.workers.values():
                feat_id = self._find_feature_id_for_scenario(payload, scen.source_scenario_id)
                if feat_id and feat_id in worker.covered_feature_ids:
                    scen.worker_id = worker.worker_id
                    worker.scenarios.append(scen)

                    # Populating Scenario trace links and semantic identifier mapping
                    scen_ident = f"Feature_{scen.source_scenario_id}"
                    ir.semantic_identifier_map[f"scenario:{scen.source_scenario_id}"] = scen_ident
                    ir.trace_links.append(TraceLinkIR(
                        spl_ref=scen_ident,
                        source_kind="scenario",
                        source_id=str(scen.source_scenario_id)
                    ))

                    # Add trace links for each individual mapped AC ID
                    for ac_id in scen.source_acceptance_criterion_ids:
                        ir.trace_links.append(TraceLinkIR(
                            spl_ref=f"AC_{ac_id}",
                            source_kind="acceptance_criterion",
                            source_id=str(ac_id)
                        ))

    async def _extract_single_feature_scenarios(
        self,
        feat: dict,
        ask_fn: Callable[[str], Any],
        output_language: str,
    ) -> list[ScenarioIR]:
        scenarios = feat.get("scenarios", [])
        if not scenarios:
            return []

        # Format scenarios for LLM prompt
        scenarios_str = []
        for s in scenarios:
            ac_list = []
            for ac in s.get("acceptance_criteria", []):
                ac_list.append(f"- AC_{ac.get('criterion_id')}: {ac.get('criterion_content')}")
            scenarios_str.append(
                f"Scenario_{s.get('scenario_id')}: {s.get('scenario_name')}\n"
                f"Content: {s.get('scenario_content')}\n"
                f"Acceptance Criteria:\n" + "\n".join(ac_list)
            )

        prompt = AC_TO_SCENARIO_PROMPT.format(
            feature_name=feat.get("feature_name"),
            feature_description=feat.get("feature_description"),
            scenarios="\n\n".join(scenarios_str),
            output_language=output_language,
        )

        res = await ask_fn(prompt)
        if not isinstance(res, dict) or not isinstance(res.get("scenarios"), list):
            raise ValueError("spl_semantic_invalid_scenario_output")
        parsed_scenarios = []
        for scenario in res["scenarios"]:
            if not scenario.get("source_scenario_id") or not scenario.get("scenario_name"):
                raise ValueError("spl_semantic_invalid_scenario")
            parsed_scenarios.append(ScenarioIR(
                source_scenario_id=scenario["source_scenario_id"],
                source_acceptance_criterion_ids=scenario.get("source_acceptance_criterion_ids", []),
                scenario_name=scenario["scenario_name"],
                flow_type=scenario.get("flow_type", "normal"),
                given=scenario.get("given", []),
                when=scenario.get("when", []),
                then=scenario.get("then", [])
            ))
        return parsed_scenarios

    def _find_feature_id_for_scenario(self, payload: SplExportInputDict, scenario_id: int) -> int | None:
        for feat in payload.get("features", []):
            for scen in feat.get("scenarios", []):
                if scen.get("scenario_id") == scenario_id:
                    return feat.get("feature_id")
        return None

    async def _run_llm_coverage_review_async(self, payload: SplExportInputDict, ir: SplSemanticIR, val_report: dict[str, Any]) -> None:
        orig_features = [f.get("feature_name") for f in payload.get("features", [])]
        orig_flows = [f.get("flow_name") for f in payload.get("flows", [])]
        orig_bos = [b.get("business_object_name") for b in payload.get("business_objects", [])]

        gen_types = [t.type_name for t in ir.types.values()]
        gen_workers = {w.worker_name: [step.command_text for step in w.main_flow] for w in ir.workers.values()}

        prompt = COVERAGE_REVIEW_PROMPT.format(
            original_features=orig_features,
            original_flows=orig_flows,
            original_business_objects=orig_bos,
            generated_types=gen_types,
            generated_workers=gen_workers,
            output_language=_output_language(payload),
        )

        res = await asyncio.wait_for(
            asyncio.to_thread(self._ask_json, prompt),
            timeout=20.0
        )
        for risk in res.get("semantic_risks", []):
            ir.warnings.append(SplExportWarningIR(
                code="llm_coverage_warning",
                message=_localized(
                    payload,
                    f"大模型审查指出设计风险: {risk}",
                    f"The LLM review identified a design risk: {risk}",
                ),
                source=WarningSourceIR(kind="project", id=ir.project_id)
            ))
            val_report["semantic_risks"].append(_localized(
                payload,
                f"大模型审查: {risk}",
                f"LLM review: {risk}",
            ))
        if not res.get("coverage_passed", True):
            val_report["coverage_passed"] = False
