from __future__ import annotations

import logging
from typing import Any

from .ir import SplExportWarningIR, SplSemanticIR, WarningSourceIR

logger = logging.getLogger(__name__)


class SplSemanticValidator:
    """
    Validates structural consistency, reference integrity, and leaf feature coverage
    for the compiled SplSemanticIR.
    """

    def __init__(self) -> None:
        pass

    def validate(self, ir: SplSemanticIR) -> dict[str, Any]:
        warnings: list[SplExportWarningIR] = []
        semantic_risks: list[str] = []
        is_english = ir.raw.get("export_options", {}).get("language") == "en-US"
        def text(zh_cn: str, en_us: str) -> str:
            return en_us if is_english else zh_cn

        covered_feat_ids, current_leaf_ids, missing_feat_ids = self._check_feature_coverage(
            ir, warnings, semantic_risks, text
        )
        self._check_type_references(ir, warnings, semantic_risks, text)
        unmapped_flow_ids = self._check_flow_coverage(
            ir, warnings, semantic_risks, text
        )
        self._check_identifier_uniqueness(ir, warnings, semantic_risks, text)
        unmapped_ac_ids = self._check_acceptance_coverage(
            ir, warnings, semantic_risks, text
        )
        self._check_judgment_paths(ir, warnings, semantic_risks, text)
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

    @staticmethod
    def _check_feature_coverage(ir, warnings, risks, text):
        features = ir.raw.get("features", [])
        children = {
            child_id
            for feature in features
            for child_id in feature.get("children_ids", [])
        }
        current = {
            feature.get("feature_id")
            for feature in features
            if feature.get("feature_id") not in children
            and ((feature.get("scope") or {}).get("scope_status") or "current") == "current"
        }
        covered = {
            feature_id
            for worker in ir.workers.values()
            for feature_id in worker.covered_feature_ids
        }
        missing = sorted(current - covered)
        for feature_id in missing:
            name = next((f.get("feature_name", "") for f in features if f.get("feature_id") == feature_id), "Unknown")
            warnings.append(SplExportWarningIR(
                code="uncovered_feature",
                message=text(
                    f"叶子功能 Feature_{feature_id} '{name}' 未被任何业务流 Worker 覆盖。",
                    f"Leaf feature Feature_{feature_id} '{name}' is not covered by any flow worker.",
                ),
                source=WarningSourceIR(kind="feature", id=str(feature_id)),
            ))
            risks.append(text(
                f"功能 Feature_{feature_id} '{name}' 未被任何业务流覆盖。",
                f"Feature Feature_{feature_id} '{name}' is not covered by any flow.",
            ))
        return covered, current, missing

    @staticmethod
    def _check_type_references(ir, warnings, risks, text):
        declared = {value.type_name for value in ir.types.values()}
        declared.update(
            field.spl_type
            for value in ir.types.values()
            for field in value.fields
            if field.enum_candidates
        )
        for worker in ir.workers.values():
            for direction, refs in (("input", worker.inputs), ("output", worker.outputs)):
                for ref in refs:
                    if ref in declared:
                        continue
                    warnings.append(SplExportWarningIR(
                        code="missing_type_ref",
                        message=text(
                            f"Worker '{worker.worker_name}' 引入了未声明的{'输入' if direction == 'input' else '输出'}类型 '{ref}'。",
                            f"Worker '{worker.worker_name}' references undeclared {direction} type '{ref}'.",
                        ),
                        source=WarningSourceIR(kind="flow", id=str(worker.source_flow_id)),
                    ))
                    risks.append(text(
                        f"Worker '{worker.worker_name}' 引用了未定义的类型 '{ref}'。",
                        f"Worker '{worker.worker_name}' references undefined type '{ref}'.",
                    ))

    @staticmethod
    def _check_flow_coverage(ir, warnings, risks, text):
        flows = ir.raw.get("flows", [])
        missing = sorted(
            {flow.get("flow_id") for flow in flows}
            - {worker.source_flow_id for worker in ir.workers.values()}
        )
        for flow_id in missing:
            name = next((f.get("flow_name", "") for f in flows if f.get("flow_id") == flow_id), "Unknown")
            warnings.append(SplExportWarningIR(
                code="unmapped_flow",
                message=text(
                    f"业务流 Flow_{flow_id} '{name}' 未能生成对应的 Worker。",
                    f"Flow Flow_{flow_id} '{name}' has no generated worker.",
                ),
                source=WarningSourceIR(kind="flow", id=str(flow_id)),
            ))
            risks.append(text(
                f"业务流程 Flow_{flow_id} '{name}' 丢失，未能转换。",
                f"Flow Flow_{flow_id} '{name}' was not converted.",
            ))
        return missing

    @staticmethod
    def _check_identifier_uniqueness(ir, warnings, risks, text):
        seen = {}
        for source_key, identifier in ir.semantic_identifier_map.items():
            if identifier not in seen:
                seen[identifier] = source_key
                continue
            previous = seen[identifier]
            warnings.append(SplExportWarningIR(
                code="duplicate_semantic_identifier",
                message=f"Duplicate semantic identifier '{identifier}' detected for '{source_key}' and '{previous}'.",
                source=WarningSourceIR(kind="project", id=ir.project_id),
            ))
            risks.append(text(
                f"重复的语义标识符 '{identifier}' 在 '{source_key}' 和 '{previous}' 中被同时使用。",
                f"Duplicate semantic identifier '{identifier}' is used by both '{source_key}' and '{previous}'.",
            ))

    @staticmethod
    def _check_acceptance_coverage(ir, warnings, risks, text):
        source_feature = {}
        for feature in ir.raw.get("features", []):
            if ((feature.get("scope") or {}).get("scope_status") or "current") != "current":
                continue
            for scenario in feature.get("scenarios", []):
                for criterion in scenario.get("acceptance_criteria", []):
                    source_feature[criterion.get("criterion_id")] = feature.get("feature_id")
        mapped = {
            criterion_id
            for worker in ir.workers.values()
            for scenario in worker.scenarios
            for criterion_id in scenario.source_acceptance_criterion_ids
        }
        missing = sorted(set(source_feature) - mapped)
        for criterion_id in missing:
            warnings.append(SplExportWarningIR(
                code="uncovered_acceptance_criterion",
                message=f"Acceptance Criterion AC_{criterion_id} is not covered by any worker scenario.",
                source=WarningSourceIR(kind="feature", id=str(source_feature.get(criterion_id, 0))),
            ))
            risks.append(text(
                f"验收条件 AC_{criterion_id} 未被任何 Worker 场景覆盖。",
                f"Acceptance criterion AC_{criterion_id} is not covered by any worker scenario.",
            ))
        return missing

    @classmethod
    def _check_judgment_paths(cls, ir, warnings, risks, text):
        for worker in ir.workers.values():
            cls._check_worker_steps(
                worker.main_flow, worker.worker_name, worker.source_flow_id,
                warnings, risks, text,
            )

    @classmethod
    def _check_worker_steps(cls, steps, worker_name, flow_id, warnings, risks, text):
        for step in steps:
            branch_kinds = {sub.branch_kind for sub in step.sub_steps}
            if step.step_type == "judgment" and (
                not step.sub_steps or not ({"if", "else"} & branch_kinds)
            ):
                warnings.append(SplExportWarningIR(
                    code="judgment_branch_unresolved",
                    message=f"Judgment step '{step.command_text}' in worker '{worker_name}' has no branching paths defined.",
                    source=WarningSourceIR(kind="flow", id=str(flow_id)),
                ))
                risks.append(text(
                    f"Worker '{worker_name}' 中的判断步骤 '{step.command_text}' 缺少分支控制结构路径。",
                    f"Judgment step '{step.command_text}' in worker '{worker_name}' has no branching path.",
                ))
            if step.sub_steps:
                cls._check_worker_steps(
                    step.sub_steps, worker_name, flow_id, warnings, risks, text
                )
