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
    ) -> NextSuggestion:
        context = await load_issue_project_context(
            project_id=project_id,
            session=session,
        )

        if not context.actors:
            return NextSuggestion(
                sourceType="generator",
                code="GENERATE_ACTORS",
                title="生成参与者",
                description="当前项目还没有参与者，建议先生成参与者。",
                action={
                    "kind": "create_draft",
                    "draft_type": "actor_generation",
                    "endpoint": "/api/actor_generation_drafts",
                    "payload": {
                        "project_id": project_id,
                    },
                },
            )

        if not context.features:
            return NextSuggestion(
                sourceType="generator",
                code="GENERATE_FEATURES",
                title="生成功能",
                description="当前项目还没有功能，建议基于参与者生成功能树。",
                action={
                    "kind": "create_draft",
                    "draft_type": "feature_generation",
                    "endpoint": "/api/feature_generation_drafts",
                    "payload": {
                        "project_id": project_id,
                    },
                },
            )

        if not context.scenarios:
            return NextSuggestion(
                sourceType="generator",
                code="GENERATE_SCENARIOS",
                title="生成场景",
                description="当前项目还没有场景，建议为功能与参与者生成场景。",
                action={
                    "kind": "create_draft",
                    "draft_type": "scenario_generation",
                    "endpoint": "/api/scenario_generation_drafts/full",
                    "payload": {
                        "project_id": project_id,
                    },
                },
            )

        # AI PerceptionSlot will be inserted here by the fixed What policy:
        # actor -> feature -> scenario -> acceptance criteria.
        return NextSuggestion(
            sourceType="predefined",
            code="ENTER_HOW",
            title="进入 How 阶段",
            description="What 阶段已有基础内容，可以继续梳理流程与业务对象。",
            action={
                "kind": "navigate",
                "route": f"/projects/{project_id}/how",
            },
        )
