from __future__ import annotations

import os
import logging
import re
import asyncio
from typing import Any, Callable, Dict, List, Optional
from .schema import SplExportInputDict, SplExportOutputDict
from .ir import SplSemanticIR, TypeIR, TypeFieldIR, WorkerIR, WorkerStepIR, ScenarioIR, SplExportWarningIR, WarningSourceIR, TraceLinkIR
from .renderer import SplSemanticRenderer, escape_string
from .validators import SplSemanticValidator
from .prompts import TYPE_NORMALIZATION_PROMPT, FLOW_TO_WORKER_PROMPT, AC_TO_SCENARIO_PROMPT, COVERAGE_REVIEW_PROMPT

logger = logging.getLogger(__name__)


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
                
        t = threading.Thread(target=run_in_thread)
        t.start()
        return fut.result()
    else:
        return asyncio.run(coro)


class SplSemanticExportSkill:
    """
    Skill to perform LLM-backed semantic compiler export of RequirementSpace models to SPL.
    Coordinates type normalization, worker mapping, Gherkin extraction, and coverage review.
    """

    def __init__(self, ask_json: Optional[Callable[[str], Dict[str, Any]]] = None) -> None:
        self._ask_json = ask_json
        self._renderer = SplSemanticRenderer()
        self._validator = SplSemanticValidator()

    def export(self, payload: SplExportInputDict) -> SplExportOutputDict:
        ir = SplSemanticIR(payload)
        
        # If LLM handler is not provided, fall back to pure placeholder shell and warn
        if not self._ask_json:
            ir.warnings.append(SplExportWarningIR(
                code="llm_unavailable",
                message="LLM client handler is not available. Using syntax-shell default rendering.",
                source=WarningSourceIR(kind="project", id=ir.project_id)
            ))
            return self._fallback_export(payload, ir)

        try:
            # Run the asynchronous compiling pipeline using run_async
            run_async(self._export_async(payload, ir))

            # Run validators and Coverage review
            val_report = self._validator.validate(ir)

            # Stage 4: Coverage review using LLM
            run_async(self._run_llm_coverage_review_async(payload, ir, val_report))

            # Render final SPL document
            spl_text = self._renderer.render(ir)

            # Quality grade determination
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

        except Exception as exc:
            logger.exception(f"Semantic compiler encountered critical error: {exc}")
            ir.warnings.append(SplExportWarningIR(
                code="semantic_compiler_error",
                message=f"Semantic compilation failed due to: {exc}. Falling back to syntax shell.",
                source=WarningSourceIR(kind="project", id=ir.project_id)
            ))
            return self._fallback_export(payload, ir)

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
                loop = asyncio.get_running_loop()
                return await asyncio.wait_for(
                    loop.run_in_executor(None, self._ask_json, prompt),
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
            bo_attributes="\n".join(attrs_str)
        )

        try:
            res = await ask_fn(prompt)
            type_name = res.get("type_name", f"BusinessObject_{bo_id}")
            
            # Sanitize PascalCase name
            type_name = re.sub(r'[^a-zA-Z0-9]', '', type_name)
            if not type_name:
                type_name = f"BusinessObject_{bo_id}"

            fields_ir = []
            for f in res.get("fields", []):
                f_name = f.get("normalized_name", "")
                f_name = re.sub(r'[^a-zA-Z0-9_]', '', f_name)
                if not f_name:
                    continue
                
                fields_ir.append(TypeFieldIR(
                    name=f_name,
                    spl_type=f.get("spl_type", "text"),
                    description=f.get("description", ""),
                    example=f.get("example", ""),
                    enum_candidates=f.get("enum_candidates", []) if f.get("is_enum") else []
                ))

            type_ir = TypeIR(type_name=type_name, source_bo_id=bo_id, fields=fields_ir)
            ir.types[str(bo_id)] = type_ir
            ir.bo_id_to_type_name[str(bo_id)] = type_name
            ir.semantic_identifier_map[f"business_object:{bo_id}"] = type_name
            ir.trace_links.append(TraceLinkIR(spl_ref=type_name, source_kind="business_object", source_id=str(bo_id)))

        except Exception as e:
            logger.warning(f"Failed to normalize Business Object {bo_id} via LLM, falling back: {e}")
            safe_type_name = f"BusinessObject_{bo_id}"
            fields_ir = []
            for attr in bo.get("business_object_attributes", []):
                attr_name = attr.get("business_object_attribute_name", "")
                safe_attr_name = re.sub(r'[^a-zA-Z0-9_]', '', attr_name) or f"field_{attr.get('business_object_attribute_id')}"
                fields_ir.append(TypeFieldIR(
                    name=safe_attr_name,
                    spl_type="text",
                    description=attr.get("business_object_attribute_description", ""),
                    example=attr.get("business_object_attribute_example", "")
                ))
            type_ir = TypeIR(type_name=safe_type_name, source_bo_id=bo_id, fields=fields_ir)
            ir.types[str(bo_id)] = type_ir
            ir.bo_id_to_type_name[str(bo_id)] = safe_type_name
            ir.semantic_identifier_map[f"business_object:{bo_id}"] = safe_type_name
            ir.trace_links.append(TraceLinkIR(spl_ref=safe_type_name, source_kind="business_object", source_id=str(bo_id)))
            ir.warnings.append(SplExportWarningIR(
                code="type_normalization_fallback",
                message=f"业务对象 BO_{bo_id} '{bo_name}' 语义类型转换失败，降级为普通属性映射。",
                source=WarningSourceIR(kind="business_object", id=str(bo_id))
            ))

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
        flow_name = flow.get("flow_name", "")
        flow_desc = flow.get("flow_description", "")
        covered_features = flow.get("feature_ids", [])
        
        steps_str = []
        for step in sorted(flow.get("flow_steps", []), key=lambda s: s.get("position", 0)):
            actor_names = [actors_mapping.get(f"Actor_{a}", "Unknown") for a in step.get("actor_ids", [])]
            input_names = [ir.bo_id_to_type_name.get(str(bi), "Unknown") for bi in step.get("input_business_object_ids", [])]
            output_names = [ir.bo_id_to_type_name.get(str(bo), "Unknown") for bo in step.get("output_business_object_ids", [])]
            
            steps_str.append(
                f"Step {step.get('position')}: {step.get('step_name')} (desc: {step.get('step_description')}, "
                f"type: {step.get('step_type')}, actors: {actor_names}, inputs: {input_names}, outputs: {output_names})"
            )

        prompt = FLOW_TO_WORKER_PROMPT.format(
            flow_name=flow_name,
            flow_description=flow_desc,
            flow_steps="\n".join(steps_str),
            types_mapping=ir.bo_id_to_type_name,
            actors_mapping=actors_mapping
        )

        try:
            res = await ask_fn(prompt)
            worker_name = res.get("worker_name", f"Flow_{flow_id}")
            worker_name = re.sub(r'[^a-zA-Z0-9]', '', worker_name)
            if not worker_name:
                worker_name = f"Flow_{flow_id}"
            
            def parse_step_node(s: dict) -> WorkerStepIR:
                return WorkerStepIR(
                    source_step_id=s.get("source_step_id"),
                    step_type=s.get("step_type", "systemAction"),
                    command_text=s.get("command_text", ""),
                    input_refs=s.get("input_refs", []),
                    output_refs=s.get("output_refs", []),
                    decision_condition=s.get("decision_condition"),
                    branch_kind=s.get("branch_kind", "sequential"),
                    sub_steps=[parse_step_node(sub) for sub in s.get("sub_steps", [])]
                )

            main_flow_ir = [parse_step_node(s) for s in res.get("main_flow_steps", [])]
            
            worker_ir = WorkerIR(
                worker_id=flow_id,
                worker_name=worker_name,
                description=res.get("description", flow_desc),
                source_flow_id=flow_id,
                covered_feature_ids=covered_features,
                actors=res.get("actors", []),
                inputs=res.get("inputs", []),
                outputs=res.get("outputs", []),
                main_flow=main_flow_ir
            )
            
            ir.workers[str(flow_id)] = worker_ir
            ir.semantic_identifier_map[f"flow:{flow_id}"] = worker_name
            ir.trace_links.append(TraceLinkIR(spl_ref=worker_name, source_kind="flow", source_id=str(flow_id)))

        except Exception as e:
            logger.warning(f"Failed to map Flow {flow_id} via LLM, falling back: {e}")
            safe_worker_name = f"Worker_Flow_{flow_id}"
            steps_ir = []
            for step in sorted(flow.get("flow_steps", []), key=lambda s: s.get("position", 0)):
                step_type = step.get("step_type", "systemAction")
                judgment_suffix = " (judgment)" if step_type == "judgment" else ""
                cmd_text = f"SystemAction: {step.get('step_name')}{judgment_suffix} ({step.get('step_description')})"
                
                steps_ir.append(WorkerStepIR(
                    source_step_id=step.get("step_id"),
                    step_type="systemAction",
                    command_text=cmd_text,
                    branch_kind="sequential"
                ))
            
            worker_ir = WorkerIR(
                worker_id=flow_id,
                worker_name=safe_worker_name,
                description=flow_desc,
                source_flow_id=flow_id,
                covered_feature_ids=covered_features,
                main_flow=steps_ir
            )
            ir.workers[str(flow_id)] = worker_ir
            ir.semantic_identifier_map[f"flow:{flow_id}"] = safe_worker_name
            ir.trace_links.append(TraceLinkIR(spl_ref=safe_worker_name, source_kind="flow", source_id=str(flow_id)))
            ir.warnings.append(SplExportWarningIR(
                code="flow_worker_fallback",
                message=f"业务流 Flow_{flow_id} '{flow_name}' 语义 Worker 转换失败，降级为普通顺序结构。",
                source=WarningSourceIR(kind="flow", id=str(flow_id))
            ))

    async def _extract_scenarios_async(self, payload: SplExportInputDict, ir: SplSemanticIR, ask_fn: Callable[[str], Any]) -> None:
        features = payload.get("features", [])
        
        # Parallel scenarios extraction for all features
        results = await asyncio.gather(*(
            self._extract_single_feature_scenarios(feat, ask_fn)
            for feat in features
        ))
        
        all_scenarios: List[ScenarioIR] = []
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

    async def _extract_single_feature_scenarios(self, feat: dict, ask_fn: Callable[[str], Any]) -> List[ScenarioIR]:
        feat_id = feat.get("feature_id")
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
            scenarios="\n\n".join(scenarios_str)
        )

        try:
            res = await ask_fn(prompt)
            parsed_scens = []
            for s in res.get("scenarios", []):
                scen_ir = ScenarioIR(
                    source_scenario_id=s.get("source_scenario_id"),
                    source_acceptance_criterion_ids=s.get("source_acceptance_criterion_ids", []),
                    scenario_name=s.get("scenario_name", "Scenario"),
                    flow_type=s.get("flow_type", "normal"),
                    given=s.get("given", []),
                    when=s.get("when", []),
                    then=s.get("then", [])
                )
                parsed_scens.append(scen_ir)
            return parsed_scens
        except Exception as e:
            logger.warning(f"Failed to parse scenarios for Feature {feat_id} via LLM, falling back: {e}")
            fallback_scens = []
            for s in scenarios:
                given = [s.get("scenario_content", "")]
                ac_ids = [ac.get("criterion_id") for ac in s.get("acceptance_criteria", [])]
                then_steps = [ac.get("criterion_content", "") for ac in s.get("acceptance_criteria", [])]
                fallback_scens.append(ScenarioIR(
                    source_scenario_id=s.get("scenario_id"),
                    source_acceptance_criterion_ids=ac_ids,
                    scenario_name=s.get("scenario_name", ""),
                    given=given,
                    when=["执行相关操作"],
                    then=then_steps
                ))
            return fallback_scens

    def _find_feature_id_for_scenario(self, payload: SplExportInputDict, scenario_id: int) -> int | None:
        for feat in payload.get("features", []):
            for scen in feat.get("scenarios", []):
                if scen.get("scenario_id") == scenario_id:
                    return feat.get("feature_id")
        return None

    async def _run_llm_coverage_review_async(self, payload: SplExportInputDict, ir: SplSemanticIR, val_report: Dict[str, Any]) -> None:
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
            generated_workers=gen_workers
        )

        try:
            loop = asyncio.get_running_loop()
            res = await asyncio.wait_for(
                loop.run_in_executor(None, self._ask_json, prompt),
                timeout=20.0
            )
            for risk in res.get("semantic_risks", []):
                ir.warnings.append(SplExportWarningIR(
                    code="llm_coverage_warning",
                    message=f"大模型审查指出设计风险: {risk}",
                    source=WarningSourceIR(kind="project", id=ir.project_id)
                ))
                val_report["semantic_risks"].append(f"大模型审查: {risk}")
            if not res.get("coverage_passed", True):
                val_report["coverage_passed"] = False
        except Exception as e:
            logger.warning(f"LLM Coverage Review step failed: {e}")

    def _fallback_export(self, payload: SplExportInputDict, ir: SplSemanticIR) -> SplExportOutputDict:
        from spl_syntax_export_skill.renderer import SplSyntaxRenderer
        renderer = SplSyntaxRenderer()
        spl_text, warnings, trace_links = renderer.render(payload)

        return {
            "spl_text": spl_text,
            "quality": "semantic_with_warnings",
            "warnings": [w.to_dict() for w in ir.warnings] + warnings,
            "trace_links": trace_links,
            "coverage_report": {
                "coverage_passed": False,
                "covered_current_feature_ids": [],
                "missing_current_feature_ids": [],
                "unmapped_flow_ids": [],
                "unmapped_acceptance_criterion_ids": [],
                "semantic_risks": ["因为编译异常降级为语法壳导出"]
            }
        }
