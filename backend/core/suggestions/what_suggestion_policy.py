from backend.core.detectors.issue_context_loader import (
    load_issue_project_context,
)
from backend.core.suggestions.stage_suggestion_policy import (
    StageSuggestionPolicy,
)
from backend.schemas import NextSuggestion


class WhatSuggestionPolicy(StageSuggestionPolicy):
    async def get_next(
        self,
        project_id: int,
        session,
        workspace_id: int,
        public_project_id: str | None = None,
    ) -> NextSuggestion:
        context = await load_issue_project_context(
            project_id=project_id,
            session=session,
            workspace_id=workspace_id,
        )
        pub_id = public_project_id or str(project_id)

        if not context.actors:
            return self._build_actor_generation_suggestion(pub_id)

        if not context.features:
            return self._build_feature_generation_suggestion(pub_id)

        leaf_without_actor = [
            f for f in context.leaf_features if len(f.actor_ids) == 0
        ]
        if leaf_without_actor:
            return self._build_actor_binding_suggestion(
                pub_id,
                leaf_without_actor[0],
            )

        if not context.scenarios:
            return self._build_scenario_generation_suggestion(pub_id)

        total_ac = sum(s.acceptance_criteria_count for s in context.scenarios)
        if total_ac == 0:
            return self._build_acceptance_criteria_suggestion(pub_id)

        return self._build_enter_how_suggestion(pub_id)

    @staticmethod
    def _build_actor_generation_suggestion(project_id: str) -> NextSuggestion:
        return NextSuggestion(
            sourceType="generator",
            code="GENERATE_ACTORS",
            title="生成参与者",
            description="当前项目还没有参与者，建议先生成参与者。",
            action={
                "kind": "create_draft",
                "draft_type": "actor_generation",
                "endpoint": "/api/actor_generation_drafts",
                "payload": {"project_id": project_id},
            },
        )

    @staticmethod
    def _build_feature_generation_suggestion(project_id: str) -> NextSuggestion:
        return NextSuggestion(
            sourceType="generator",
            code="GENERATE_FEATURES",
            title="生成功能",
            description="当前项目还没有功能，建议基于参与者生成功能树。",
            action={
                "kind": "create_draft",
                "draft_type": "feature_generation",
                "endpoint": "/api/feature_generation_drafts",
                "payload": {"project_id": project_id},
            },
        )

    @staticmethod
    def _build_actor_binding_suggestion(
        project_id: str,
        feature,
    ) -> NextSuggestion:
        return NextSuggestion(
            sourceType="predefined",
            code="BIND_ACTORS_TO_FEATURE",
            title="补充功能执行角色",
            description=f"检测到叶子功能“{feature.name}”尚未绑定任何执行角色，请先完成绑定。",
            target={"type": "feature", "id": feature.feature_id},
            action={
                "kind": "open_panel",
                "route": f"/projects/{project_id}/what",
                "panel": "feature",
                "payload": {"feature_id": feature.feature_id},
            },
        )

    @staticmethod
    def _build_scenario_generation_suggestion(project_id: str) -> NextSuggestion:
        return NextSuggestion(
            sourceType="generator",
            code="GENERATE_SCENARIOS",
            title="生成场景",
            description="当前项目还没有场景，建议为功能与参与者生成场景。",
            action={
                "kind": "create_draft",
                "draft_type": "scenario_generation",
                "endpoint": "/api/scenario_generation_drafts/full",
                "payload": {"project_id": project_id},
            },
        )

    @staticmethod
    def _build_acceptance_criteria_suggestion(
        project_id: str,
    ) -> NextSuggestion:
        return NextSuggestion(
            sourceType="generator",
            code="GENERATE_ACCEPTANCE_CRITERIA",
            title="生成验收标准",
            description="典型成功场景已生成，建议补充对应的验收标准。",
            action={
                "kind": "create_draft",
                "draft_type": "acceptance_criteria_generation",
                "endpoint": "/api/acceptance_criteria_generation_drafts/full",
                "payload": {"project_id": project_id},
            },
        )

    @staticmethod
    def _build_enter_how_suggestion(project_id: str) -> NextSuggestion:
        return NextSuggestion(
            sourceType="predefined",
            code="ENTER_HOW",
            title="进入 How 阶段",
            description="What 阶段已有基础内容，可以继续梳理流程与业务对象。",
            action={
                "kind": "stage_transition",
                "transition_action": "enter_how",
                "route": f"/projects/{project_id}/how",
            },
        )
