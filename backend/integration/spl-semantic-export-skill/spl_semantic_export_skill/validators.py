from __future__ import annotations

import logging
from typing import Dict, List, Set
from .ir import SplSemanticIR, SplExportWarningIR, WarningSourceIR

logger = logging.getLogger(__name__)


class SplSemanticValidator:
    """
    Validates structural consistency, reference integrity, and leaf feature coverage
    for the compiled SplSemanticIR.
    """

    def __init__(self) -> None:
        pass

    def validate(self, ir: SplSemanticIR) -> Dict[str, Any]:
        warnings: List[SplExportWarningIR] = []
        semantic_risks: List[str] = []

        # 1. Gather all leaf features
        features = ir.raw.get("features", [])
        children_map: Set[int] = set()
        for feat in features:
            for child_id in feat.get("children_ids", []):
                children_map.add(child_id)

        current_leaf_ids: Set[int] = set()
        for feat in features:
            feat_id = feat.get("feature_id")
            scope_obj = feat.get("scope") or {}
            scope_status = scope_obj.get("scope_status") or "current"
            
            # If no children and scope is current, it's a current leaf feature
            if feat_id not in children_map and scope_status == "current":
                current_leaf_ids.add(feat_id)

        # 2. Check which features are covered by workers
        covered_feat_ids: Set[int] = set()
        for worker in ir.workers.values():
            for fid in worker.covered_feature_ids:
                covered_feat_ids.add(fid)

        missing_feat_ids = sorted(list(current_leaf_ids - covered_feat_ids))
        for fid in missing_feat_ids:
            feat_name = next((f.get("feature_name", "") for f in features if f.get("feature_id") == fid), "Unknown")
            warnings.append(SplExportWarningIR(
                code="uncovered_feature",
                message=f"叶子功能 Feature_{fid} '{feat_name}' 未被任何业务流 Worker 覆盖。",
                source=WarningSourceIR(kind="feature", id=str(fid))
            ))
            semantic_risks.append(f"功能 Feature_{fid} '{feat_name}' 未被任何业务流覆盖。")

        # 3. Check type references in workers
        declared_type_names = {t.type_name for t in ir.types.values()}
        # Enums are also declared types
        for t in ir.types.values():
            for f in t.fields:
                if f.enum_candidates:
                    # e.g. TaskStatus or TaskPriority
                    declared_type_names.add(f.spl_type)

        for worker in ir.workers.values():
            # Check inputs
            for inp in worker.inputs:
                if inp not in declared_type_names:
                    warnings.append(SplExportWarningIR(
                        code="missing_type_ref",
                        message=f"Worker '{worker.worker_name}' 引入了未声明的输入类型 '{inp}'。",
                        source=WarningSourceIR(kind="flow", id=str(worker.source_flow_id))
                    ))
                    semantic_risks.append(f"Worker '{worker.worker_name}' 引用了未定义的类型 '{inp}'。")
            
            # Check outputs
            for out in worker.outputs:
                if out not in declared_type_names:
                    warnings.append(SplExportWarningIR(
                        code="missing_type_ref",
                        message=f"Worker '{worker.worker_name}' 引入了未声明的输出类型 '{out}'。",
                        source=WarningSourceIR(kind="flow", id=str(worker.source_flow_id))
                    ))
                    semantic_risks.append(f"Worker '{worker.worker_name}' 引用了未定义的类型 '{out}'。")

        # 4. Check if all flows have corresponding workers
        flows = ir.raw.get("flows", [])
        flow_ids = {f.get("flow_id") for f in flows}
        mapped_flow_ids = {w.source_flow_id for w in ir.workers.values()}
        
        unmapped_flow_ids = sorted(list(flow_ids - mapped_flow_ids))
        for fid in unmapped_flow_ids:
            flow_name = next((f.get("flow_name", "") for f in flows if f.get("flow_id") == fid), "Unknown")
            warnings.append(SplExportWarningIR(
                code="unmapped_flow",
                message=f"业务流 Flow_{fid} '{flow_name}' 未能生成对应的 Worker。",
                source=WarningSourceIR(kind="flow", id=str(fid))
            ))
            semantic_risks.append(f"业务流程 Flow_{fid} '{flow_name}' 丢失，未能转换。")

        # 5. Check semantic identifier uniqueness
        seen_identifiers: Dict[str, str] = {}
        for source_key, identifier in ir.semantic_identifier_map.items():
            if identifier in seen_identifiers:
                prev_key = seen_identifiers[identifier]
                warnings.append(SplExportWarningIR(
                    code="duplicate_semantic_identifier",
                    message=f"Duplicate semantic identifier '{identifier}' detected for '{source_key}' and '{prev_key}'.",
                    source=WarningSourceIR(kind="project", id=ir.project_id)
                ))
                semantic_risks.append(f"重复的语义标识符 '{identifier}' 在 '{source_key}' 和 '{prev_key}' 中被同时使用。")
            else:
                seen_identifiers[identifier] = source_key

        # 6. Check unmapped AC coverage
        all_ac_ids: Set[int] = set()
        ac_source_feat: Dict[int, int] = {}
        for feat in features:
            scope_obj = feat.get("scope") or {}
            scope_status = scope_obj.get("scope_status") or "current"
            if scope_status == "current":
                for scen in feat.get("scenarios", []):
                    for ac in scen.get("acceptance_criteria", []):
                        ac_id = ac.get("criterion_id")
                        all_ac_ids.add(ac_id)
                        ac_source_feat[ac_id] = feat.get("feature_id")

        mapped_ac_ids: Set[int] = set()
        for worker in ir.workers.values():
            for scen in worker.scenarios:
                for ac_id in scen.source_acceptance_criterion_ids:
                    mapped_ac_ids.add(ac_id)

        unmapped_ac_ids = sorted(list(all_ac_ids - mapped_ac_ids))
        for ac_id in unmapped_ac_ids:
            feat_id = ac_source_feat.get(ac_id, 0)
            warnings.append(SplExportWarningIR(
                code="uncovered_acceptance_criterion",
                message=f"Acceptance Criterion AC_{ac_id} is not covered by any worker scenario.",
                source=WarningSourceIR(kind="feature", id=str(feat_id))
            ))
            semantic_risks.append(f"验收条件 AC_{ac_id} 未被任何 Worker 场景覆盖。")

        # 7. Check judgment branching paths recursively
        def check_steps(steps: List[WorkerStepIR], worker_name: str, flow_id: int):
            for step in steps:
                if step.step_type == "judgment":
                    branch_kinds = {s.branch_kind for s in step.sub_steps}
                    if not step.sub_steps or not ("if" in branch_kinds or "else" in branch_kinds):
                        warnings.append(SplExportWarningIR(
                            code="judgment_branch_unresolved",
                            message=f"Judgment step '{step.command_text}' in worker '{worker_name}' has no branching paths defined.",
                            source=WarningSourceIR(kind="flow", id=str(flow_id))
                        ))
                        semantic_risks.append(f"Worker '{worker_name}' 中的判断步骤 '{step.command_text}' 缺少分支控制结构路径。")
                if step.sub_steps:
                    check_steps(step.sub_steps, worker_name, flow_id)

        for worker in ir.workers.values():
            check_steps(worker.main_flow, worker.worker_name, worker.source_flow_id)

        # Add warnings to the IR object
        ir.warnings.extend(warnings)

        has_judgment_unresolved = any(w.code == "judgment_branch_unresolved" for w in warnings)
        has_duplicate_identifier = any(w.code == "duplicate_semantic_identifier" for w in warnings)

        coverage_passed = (len(missing_feat_ids) == 0 and 
                           len(unmapped_flow_ids) == 0 and 
                           len(unmapped_ac_ids) == 0 and
                           not has_judgment_unresolved and
                           not has_duplicate_identifier)

        return {
            "coverage_passed": coverage_passed,
            "covered_current_feature_ids": sorted(list(covered_feat_ids & current_leaf_ids)),
            "missing_current_feature_ids": missing_feat_ids,
            "unmapped_flow_ids": unmapped_flow_ids,
            "unmapped_acceptance_criterion_ids": unmapped_ac_ids,
            "semantic_risks": semantic_risks
        }
