from backend.core.detectors.base_issue_detector import BaseIssueDetector
from backend.core.detectors.issue_context_loader import (
    IssueProjectContext,
    load_issue_project_context,
)
from backend.schemas import (
    Issue,
    IssueSeverity,
    IssueStage,
    IssueTarget,
)


class WhatIssueDetector(BaseIssueDetector):
    async def detect(self, project_id: int, session) -> list[Issue]:
        context = await load_issue_project_context(
            project_id=project_id,
            session=session,
        )

        issues: list[Issue] = []
        issues.extend(self._detect_actor_without_feature(context))
        issues.extend(self._detect_leaf_feature_without_actor(context))
        issues.extend(
            self._detect_feature_actor_pair_without_scenario(context)
        )
        issues.extend(
            self._detect_scenario_actor_not_in_feature_actors(context)
        )
        issues.extend(self._detect_scenario_without_acceptance_criteria(context))
        issues.extend(self._detect_duplicate_scenario_name(context))

        return issues

    @staticmethod
    def _detect_actor_without_feature(
        context: IssueProjectContext,
    ) -> list[Issue]:
        actor_feature_count = {
            actor.actor_id: 0
            for actor in context.actors
        }

        for feature in context.features:
            for actor_id in feature.actor_ids:
                if actor_id in actor_feature_count:
                    actor_feature_count[actor_id] += 1

        return [
            Issue(
                code="ACTOR_WITHOUT_FEATURE",
                stage=IssueStage.WHAT,
                severity=IssueSeverity.WARNING,
                title="角色未关联功能",
                description=f"角色“{actor.name}”还没有关联任何功能。",
                target=IssueTarget(
                    targetType="actor",
                    targetId=actor.actor_id,
                ),
                actionCode="open_actor_feature_relation_panel",
            )
            for actor in context.actors
            if actor_feature_count.get(actor.actor_id, 0) == 0
        ]

    @staticmethod
    def _detect_leaf_feature_without_actor(
        context: IssueProjectContext,
    ) -> list[Issue]:
        leaf_features = context.leaf_features
        with_actor = [f for f in leaf_features if f.actor_ids]

        # Non-equilibrium: if all leaf features lack actors (or there are no leaf features),
        # do not report issues; suggest role-binding / actor-generation instead.
        if len(leaf_features) > 0 and len(with_actor) == 0:
            return []

        return [
            Issue(
                code="LEAF_FEATURE_WITHOUT_ACTOR",
                stage=IssueStage.WHAT,
                severity=IssueSeverity.BLOCKING,
                title="叶子功能缺少参与者",
                description=f"叶子功能“{feature.name}”还没有关联参与者。",
                target=IssueTarget(
                    targetType="feature",
                    targetId=feature.feature_id,
                ),
                actionCode="open_feature_actor_relation_panel",
            )
            for feature in leaf_features
            if len(feature.actor_ids) == 0
        ]

    @staticmethod
    def _detect_feature_actor_pair_without_scenario(
        context: IssueProjectContext,
    ) -> list[Issue]:
        # Non-equilibrium: if there are no scenarios at all, do not report pair issues;
        # let suggestion policy recommend GENERATE_SCENARIOS.
        if not context.scenarios:
            return []

        scenario_pair_set = {
            (
                scenario.feature_id,
                scenario.actor_id,
            )
            for scenario in context.scenarios
        }

        actor_name_map = {
            actor.actor_id: actor.name
            for actor in context.actors
        }

        issues: list[Issue] = []

        for feature in context.leaf_features:
            for actor_id in feature.actor_ids:
                if (feature.feature_id, actor_id) in scenario_pair_set:
                    continue

                actor_name = actor_name_map.get(actor_id, str(actor_id))

                issues.append(
                    Issue(
                        code="FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO",
                        stage=IssueStage.WHAT,
                        severity=IssueSeverity.WARNING,
                        title="功能与参与者组合缺少场景",
                        description=(
                            f"功能“{feature.name}”与参与者“{actor_name}”"
                            "还没有对应场景。"
                        ),
                        target=IssueTarget(
                            targetType="feature_actor_pair",
                            targetId=(
                                f"{feature.feature_id}:{actor_id}"
                            ),
                        ),
                        actionCode=(
                            "create_single_scenario_generation_draft"
                        ),
                        metadata={
                            "feature_id": feature.feature_id,
                            "actor_id": actor_id,
                        },
                    )
                )

        return issues

    @staticmethod
    def _detect_scenario_actor_not_in_feature_actors(
        context: IssueProjectContext,
    ) -> list[Issue]:
        feature_actor_ids = {
            feature.feature_id: set(feature.actor_ids)
            for feature in context.features
        }

        actor_name_map = {
            actor.actor_id: actor.name
            for actor in context.actors
        }

        issues: list[Issue] = []

        for scenario in context.scenarios:
            actor_ids = feature_actor_ids.get(scenario.feature_id, set())

            if scenario.actor_id in actor_ids:
                continue

            actor_name = actor_name_map.get(scenario.actor_id, str(scenario.actor_id))

            issues.append(
                Issue(
                    code="SCENARIO_ACTOR_NOT_IN_FEATURE_ACTORS",
                    stage=IssueStage.WHAT,
                    severity=IssueSeverity.BLOCKING,
                    title="场景参与者与功能关联不一致",
                    description=(
                        f"场景“{scenario.name}”引用的参与者 "
                        f"“{actor_name}”未关联到该功能。"
                    ),
                    target=IssueTarget(
                        targetType="scenario",
                        targetId=scenario.scenario_id,
                    ),
                    actionCode="open_scenario_relation_panel",
                    metadata={
                        "feature_id": scenario.feature_id,
                        "actor_id": scenario.actor_id,
                    },
                )
            )

        return issues

    @staticmethod
    def _detect_scenario_without_acceptance_criteria(
        context: IssueProjectContext,
    ) -> list[Issue]:
        # Non-equilibrium: if there are no scenarios or no scenarios have any AC,
        # do not report individual issues; let suggestion policy handle it.
        if not context.scenarios:
            return []

        total_ac = sum(s.acceptance_criteria_count for s in context.scenarios)
        if total_ac == 0:
            return []

        return [
            Issue(
                code="SCENARIO_WITHOUT_ACCEPTANCE_CRITERIA",
                stage=IssueStage.WHAT,
                severity=IssueSeverity.WARNING,
                title="场景缺少成功标准",
                description=f"场景“{scenario.name}”还没有成功标准。",
                target=IssueTarget(
                    targetType="scenario",
                    targetId=scenario.scenario_id,
                ),
                actionCode="create_acceptance_criteria_generation_draft",
            )
            for scenario in context.scenarios
            if scenario.acceptance_criteria_count == 0
        ]

    @staticmethod
    def _detect_duplicate_scenario_name(
        context: IssueProjectContext,
    ) -> list[Issue]:
        group_map: dict[tuple[int, int, str], list[int]] = {}

        for scenario in context.scenarios:
            key = (
                scenario.feature_id,
                scenario.actor_id,
                scenario.name.strip(),
            )
            group_map.setdefault(key, []).append(scenario.scenario_id)

        actor_name_map = {
            actor.actor_id: actor.name
            for actor in context.actors
        }
        feature_name_map = {
            feature.feature_id: feature.name
            for feature in context.features
        }

        issues: list[Issue] = []

        for (feature_id, actor_id, scenario_name), scenario_ids in (
            group_map.items()
        ):
            if not scenario_name or len(scenario_ids) <= 1:
                continue

            feature_name = feature_name_map.get(feature_id, str(feature_id))
            actor_name = actor_name_map.get(actor_id, str(actor_id))

            issues.append(
                Issue(
                    code="DUPLICATE_SCENARIO_NAME",
                    stage=IssueStage.WHAT,
                    severity=IssueSeverity.INFO,
                    title="场景名称重复",
                    description=(
                        f"功能“{feature_name}”与参与者“{actor_name}”下存在"
                        f"重复场景名称“{scenario_name}”。"
                    ),
                    target=IssueTarget(
                        targetType="scenario_group",
                        targetId=":".join(
                            str(scenario_id)
                            for scenario_id in scenario_ids
                        ),
                    ),
                    actionCode="open_scenario_merge_panel",
                    metadata={
                        "feature_id": feature_id,
                        "actor_id": actor_id,
                        "scenario_ids": scenario_ids,
                    },
                )
            )

        return issues
