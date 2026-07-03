from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.detectors import WhatIssueDetector, HowIssueDetector, ScopeIssueDetector
from backend.database.model import (
    ProjectModel,
    ActorModel,
    FeatureModel,
    FeatureRelationModel,
    ScenarioModel,
    ScenarioAcceptanceCriterionModel,
    FlowModel,
    FlowStepModel,
    BusinessObjectModel,
    BusinessObjectAttributeModel,
    ScopeModel,
    feature_actor_table,
    flow_step_actor_table,
    flow_step_input_business_object_table,
    flow_step_output_business_object_table,
)
from backend.schemas import IssueSeverity


class StageGateEvaluator:
    def __init__(self) -> None:
        self.what_detector = WhatIssueDetector()
        self.how_detector = HowIssueDetector()
        self.scope_detector = ScopeIssueDetector()

    async def evaluate_gates(self, project_id: int, session: AsyncSession) -> dict[str, bool]:
        """
        Evaluate absolute What/How/Scope gate readiness states in Python.
        Returns a dict e.g. {"what": True, "how": False, "scope": False}.
        """
        project = await session.get(ProjectModel, project_id)
        if not project:
            return {"what": False, "how": False, "scope": False}

        # 1. Detect issues for each stage using existing detectors
        what_issues = await self.what_detector.detect(project_id, session)
        how_issues = await self.how_detector.detect(project_id, session)
        scope_issues = await self.scope_detector.detect(project_id, session)

        # 2. Query structural models count and properties
        actors_result = await session.execute(
            select(ActorModel.id).where(ActorModel.project_id == project_id)
        )
        actor_ids = actors_result.scalars().all()
        actors_count = len(actor_ids)
        actor_id_set = set(actor_ids)

        features_result = await session.execute(
            select(FeatureModel).where(FeatureModel.project_id == project_id)
        )
        features = features_result.scalars().all()

        feature_ids = [f.id for f in features]
        parent_ids: set[int] = set()
        if feature_ids:
            relations_result = await session.execute(
                select(FeatureRelationModel.parent_feature_id).where(
                    FeatureRelationModel.parent_feature_id.in_(feature_ids),
                    FeatureRelationModel.child_feature_id.in_(feature_ids),
                )
            )
            parent_ids = set(relations_result.scalars().all())
        leaf_features = [f for f in features if f.id not in parent_ids]

        feature_actor_rows = (await session.execute(
            select(feature_actor_table.c.feature_id, feature_actor_table.c.actor_id)
            .join(FeatureModel, FeatureModel.id == feature_actor_table.c.feature_id)
            .where(FeatureModel.project_id == project_id)
        )).all()
        feature_actor_map: dict[int, list[int]] = {}
        for feature_id, actor_id in feature_actor_rows:
            feature_actor_map.setdefault(feature_id, []).append(actor_id)

        scenarios_result = await session.execute(
            select(ScenarioModel)
            .join(FeatureModel, FeatureModel.id == ScenarioModel.feature_id)
            .where(FeatureModel.project_id == project_id)
        )
        scenarios = scenarios_result.scalars().all()
        scenario_ids = [s.id for s in scenarios]
        feature_scenario_map: dict[int, list[int]] = {}
        for scenario in scenarios:
            feature_scenario_map.setdefault(scenario.feature_id, []).append(scenario.id)

        ac_scenario_ids: set[int] = set()
        if scenario_ids:
            ac_result = await session.execute(
                select(ScenarioAcceptanceCriterionModel.scenario_id).where(
                    ScenarioAcceptanceCriterionModel.scenario_id.in_(scenario_ids)
                )
            )
            ac_scenario_ids = set(ac_result.scalars().all())

        # 3. Evaluate What Stage Gate
        # What stage passes under the same hard structural rules as StageProgress:
        # actor, leaf feature, leaf actor binding, leaf scenario, scenario AC, no blockers.
        what_has_blocking = any(
            issue.severity == IssueSeverity.BLOCKING for issue in what_issues
        )
        leaf_without_actor = [f for f in leaf_features if not feature_actor_map.get(f.id)]
        leaf_without_scenario = [f for f in leaf_features if not feature_scenario_map.get(f.id)]
        scenarios_without_ac = [sid for sid in scenario_ids if sid not in ac_scenario_ids]
        what_passed = (
            actors_count > 0
            and len(leaf_features) > 0
            and not leaf_without_actor
            and not leaf_without_scenario
            and not scenarios_without_ac
            and not what_has_blocking
        )

        # 4. Evaluate How Stage Gate
        # How stage passes under the same hard structural rules as StageProgress:
        # flow, flow steps, no invalid step references, object attributes if objects exist, no blockers.
        flows = (await session.execute(
            select(FlowModel).where(FlowModel.project_id == project_id)
        )).scalars().all()
        flow_ids = [flow.id for flow in flows]

        steps: list[FlowStepModel] = []
        flows_with_steps: set[int] = set()
        step_actor_map: dict[int, list[int]] = {}
        step_input_bo_map: dict[int, list[int]] = {}
        step_output_bo_map: dict[int, list[int]] = {}
        if flow_ids:
            steps = (await session.execute(
                select(FlowStepModel).where(FlowStepModel.flow_id.in_(flow_ids))
            )).scalars().all()
            flows_with_steps = {step.flow_id for step in steps}
            step_ids = [step.id for step in steps]
            if step_ids:
                step_actor_rows = (await session.execute(
                    select(flow_step_actor_table.c.flow_step_id, flow_step_actor_table.c.actor_id)
                    .where(flow_step_actor_table.c.flow_step_id.in_(step_ids))
                )).all()
                for step_id, actor_id in step_actor_rows:
                    step_actor_map.setdefault(step_id, []).append(actor_id)

                step_input_bo_rows = (await session.execute(
                    select(
                        flow_step_input_business_object_table.c.flow_step_id,
                        flow_step_input_business_object_table.c.business_object_id,
                    ).where(flow_step_input_business_object_table.c.flow_step_id.in_(step_ids))
                )).all()
                for step_id, bo_id in step_input_bo_rows:
                    step_input_bo_map.setdefault(step_id, []).append(bo_id)

                step_output_bo_rows = (await session.execute(
                    select(
                        flow_step_output_business_object_table.c.flow_step_id,
                        flow_step_output_business_object_table.c.business_object_id,
                    ).where(flow_step_output_business_object_table.c.flow_step_id.in_(step_ids))
                )).all()
                for step_id, bo_id in step_output_bo_rows:
                    step_output_bo_map.setdefault(step_id, []).append(bo_id)

        bo_ids = (await session.execute(
            select(BusinessObjectModel.id).where(BusinessObjectModel.project_id == project_id)
        )).scalars().all()
        bo_id_set = set(bo_ids)

        object_attribute_count = 0
        if bo_ids:
            object_attribute_count = len((await session.execute(
                select(BusinessObjectAttributeModel.id).where(
                    BusinessObjectAttributeModel.business_object_id.in_(bo_ids)
                )
            )).scalars().all())

        how_has_blocking = any(
            issue.severity == IssueSeverity.BLOCKING for issue in how_issues
        )
        flows_without_steps = [flow_id for flow_id in flow_ids if flow_id not in flows_with_steps]
        invalid_actor_steps = [
            step for step in steps
            if any(actor_id not in actor_id_set for actor_id in step_actor_map.get(step.id, []))
        ]
        invalid_bo_steps = []
        for step in steps:
            step_bo_ids = step_input_bo_map.get(step.id, []) + step_output_bo_map.get(step.id, [])
            if any(bo_id not in bo_id_set for bo_id in step_bo_ids):
                invalid_bo_steps.append(step)
        missing_object_attributes = bool(bo_ids) and object_attribute_count == 0

        how_passed = (
            what_passed
            and len(flow_ids) > 0
            and not flows_without_steps
            and not invalid_actor_steps
            and not invalid_bo_steps
            and not missing_object_attributes
            and not how_has_blocking
        )

        # 5. Evaluate Scope Stage Gate
        # Scope stage passes if:
        # - What and How stages have passed.
        # - Kano status is 'generated' or 'skipped'.
        # - Every leaf feature has a scope status decision.
        # - Has no BLOCKING issues.
        scopes_result = await session.execute(
            select(ScopeModel)
            .join(FeatureModel)
            .where(FeatureModel.project_id == project_id)
        )
        scopes = scopes_result.scalars().all()
        scoped_feature_ids = {s.feature_id for s in scopes if s.status}

        all_leaf_features_scoped = len(leaf_features) > 0 and all(
            lf.id in scoped_feature_ids for lf in leaf_features
        )
        kano_ready = project.kano_status in ("generated", "skipped")

        scope_has_blocking = any(
            issue.severity == IssueSeverity.BLOCKING for issue in scope_issues
        )

        scope_passed = (
            what_passed
            and how_passed
            and all_leaf_features_scoped
            and kano_ready
            and not scope_has_blocking
        )

        return {
            "what": bool(what_passed),
            "how": bool(how_passed),
            "scope": bool(scope_passed),
        }
