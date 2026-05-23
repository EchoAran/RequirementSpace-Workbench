from backend.core.detectors.base_issue_detector import BaseIssueDetector
from backend.core.detectors.issue_context_loader import (
    FlowIssueItem,
    IssueProjectContext,
    load_issue_project_context,
)
from backend.schemas import (
    Issue,
    IssueSeverity,
    IssueStage,
    IssueTarget,
)


class HowIssueDetector(BaseIssueDetector):
    async def detect(self, project_id: int, session) -> list[Issue]:
        context = await load_issue_project_context(
            project_id=project_id,
            session=session,
        )

        issues: list[Issue] = []
        issues.extend(self._detect_leaf_feature_without_flow(context))
        issues.extend(self._detect_flow_without_feature(context))
        issues.extend(self._detect_flow_without_steps(context))
        issues.extend(self._detect_actor_action_step_without_actor(context))
        issues.extend(self._detect_judgment_step_with_too_few_branches(context))
        issues.extend(self._detect_unreachable_flow_step(context))
        issues.extend(self._detect_business_object_without_usage(context))
        issues.extend(self._detect_business_object_without_attributes(context))

        return issues

    @staticmethod
    def _detect_leaf_feature_without_flow(
        context: IssueProjectContext,
    ) -> list[Issue]:
        flow_feature_ids = {
            feature_id
            for flow in context.flows
            for feature_id in flow.feature_ids
        }

        return [
            Issue(
                code="LEAF_FEATURE_WITHOUT_FLOW",
                stage=IssueStage.HOW,
                severity=IssueSeverity.WARNING,
                title="叶子功能缺少流程覆盖",
                description=f"叶子功能“{feature.name}”还没有被流程覆盖。",
                target=IssueTarget(
                    targetType="feature",
                    targetId=feature.feature_id,
                ),
                resolverCode="open_flow_feature_panel",
            )
            for feature in context.leaf_features
            if feature.feature_id not in flow_feature_ids
        ]

    @staticmethod
    def _detect_flow_without_feature(
        context: IssueProjectContext,
    ) -> list[Issue]:
        return [
            Issue(
                code="FLOW_WITHOUT_FEATURE",
                stage=IssueStage.HOW,
                severity=IssueSeverity.BLOCKING,
                title="流程未关联功能",
                description=f"流程“{flow.name}”还没有关联任何功能。",
                target=IssueTarget(
                    targetType="flow",
                    targetId=flow.flow_id,
                ),
                resolverCode="open_flow_feature_panel",
            )
            for flow in context.flows
            if len(flow.feature_ids) == 0
        ]

    @staticmethod
    def _detect_flow_without_steps(
        context: IssueProjectContext,
    ) -> list[Issue]:
        return [
            Issue(
                code="FLOW_WITHOUT_STEPS",
                stage=IssueStage.HOW,
                severity=IssueSeverity.BLOCKING,
                title="流程缺少步骤",
                description=f"流程“{flow.name}”还没有任何步骤。",
                target=IssueTarget(
                    targetType="flow",
                    targetId=flow.flow_id,
                ),
                resolverCode="open_flow_editor",
            )
            for flow in context.flows
            if len(flow.steps) == 0
        ]

    @staticmethod
    def _detect_actor_action_step_without_actor(
        context: IssueProjectContext,
    ) -> list[Issue]:
        issues: list[Issue] = []

        for flow in context.flows:
            for step in flow.steps:
                if step.step_type != "actorAction" or step.actor_ids:
                    continue

                issues.append(
                    Issue(
                        code="ACTOR_ACTION_STEP_WITHOUT_ACTOR",
                        stage=IssueStage.HOW,
                        severity=IssueSeverity.BLOCKING,
                        title="用户动作步骤缺少参与者",
                        description=(
                            f"流程“{flow.name}”中的步骤“{step.name}”"
                            "是用户动作，但没有关联参与者。"
                        ),
                        target=IssueTarget(
                            targetType="flow_step",
                            targetId=step.step_id,
                            parentType="flow",
                            parentId=flow.flow_id,
                        ),
                        resolverCode="open_flow_step_actor_panel",
                    )
                )

        return issues

    @staticmethod
    def _detect_judgment_step_with_too_few_branches(
        context: IssueProjectContext,
    ) -> list[Issue]:
        issues: list[Issue] = []

        for flow in context.flows:
            for step in flow.steps:
                if step.step_type != "judgment":
                    continue

                if len(step.next_step_ids) >= 2:
                    continue

                issues.append(
                    Issue(
                        code="JUDGMENT_STEP_WITH_TOO_FEW_BRANCHES",
                        stage=IssueStage.HOW,
                        severity=IssueSeverity.WARNING,
                        title="判断步骤分支不足",
                        description=(
                            f"流程“{flow.name}”中的判断步骤“{step.name}”"
                            "少于两个后继分支。"
                        ),
                        target=IssueTarget(
                            targetType="flow_step",
                            targetId=step.step_id,
                            parentType="flow",
                            parentId=flow.flow_id,
                        ),
                        resolverCode="open_flow_step_next_panel",
                    )
                )

        return issues

    @classmethod
    def _detect_unreachable_flow_step(
        cls,
        context: IssueProjectContext,
    ) -> list[Issue]:
        issues: list[Issue] = []

        for flow in context.flows:
            unreachable_steps = cls._find_unreachable_steps(flow)

            for step_id in unreachable_steps:
                step = next(
                    item
                    for item in flow.steps
                    if item.step_id == step_id
                )
                issues.append(
                    Issue(
                        code="UNREACHABLE_FLOW_STEP",
                        stage=IssueStage.HOW,
                        severity=IssueSeverity.WARNING,
                        title="流程步骤不可达",
                        description=(
                            f"流程“{flow.name}”中的步骤“{step.name}”"
                            "无法从第一个步骤到达。"
                        ),
                        target=IssueTarget(
                            targetType="flow_step",
                            targetId=step.step_id,
                            parentType="flow",
                            parentId=flow.flow_id,
                        ),
                        resolverCode="open_flow_editor",
                    )
                )

        return issues

    @staticmethod
    def _find_unreachable_steps(flow: FlowIssueItem) -> set[int]:
        if len(flow.steps) <= 1:
            return set()

        step_ids = {
            step.step_id
            for step in flow.steps
        }
        first_step_id = flow.steps[0].step_id

        visited: set[int] = set()
        stack = [first_step_id]

        while stack:
            step_id = stack.pop()

            if step_id in visited:
                continue

            visited.add(step_id)

            step = next(
                item
                for item in flow.steps
                if item.step_id == step_id
            )

            for next_step_id in step.next_step_ids:
                if next_step_id in step_ids:
                    stack.append(next_step_id)

        return step_ids - visited

    @staticmethod
    def _detect_business_object_without_usage(
        context: IssueProjectContext,
    ) -> list[Issue]:
        return [
            Issue(
                code="BUSINESS_OBJECT_WITHOUT_USAGE",
                stage=IssueStage.HOW,
                severity=IssueSeverity.INFO,
                title="业务对象未被流程使用",
                description=f"业务对象“{item.name}”没有被任何流程步骤使用。",
                target=IssueTarget(
                    targetType="business_object",
                    targetId=item.business_object_id,
                ),
                resolverCode="open_business_object_usage_panel",
            )
            for item in context.business_objects
            if item.usage_count == 0
        ]

    @staticmethod
    def _detect_business_object_without_attributes(
        context: IssueProjectContext,
    ) -> list[Issue]:
        return [
            Issue(
                code="BUSINESS_OBJECT_WITHOUT_ATTRIBUTES",
                stage=IssueStage.HOW,
                severity=IssueSeverity.INFO,
                title="业务对象缺少属性",
                description=f"业务对象“{item.name}”还没有属性。",
                target=IssueTarget(
                    targetType="business_object",
                    targetId=item.business_object_id,
                ),
                resolverCode="open_business_object_attribute_panel",
            )
            for item in context.business_objects
            if item.attribute_count == 0
        ]
