from backend.core.detectors.issue_context_loader import (
    load_issue_project_context,
)
from backend.core.suggestions.stage_suggestion_policy import (
    StageSuggestionPolicy,
)
from backend.schemas import NextSuggestion


class ScopeSuggestionPolicy(StageSuggestionPolicy):
    async def get_next(
        self,
        project_id: int,
        session,
    ) -> NextSuggestion:
        context = await load_issue_project_context(
            project_id=project_id,
            session=session,
        )

        if not context.scopes:
            return NextSuggestion(
                sourceType="generator",
                code="GENERATE_SCOPE",
                title="生成功能范围",
                description="当前项目还没有范围结论，建议生成功能范围草稿。",
                action={
                    "kind": "create_draft",
                    "draft_type": "scope_generation",
                    "endpoint": "/api/scope_generation_drafts",
                    "payload": {
                        "project_id": project_id,
                    },
                },
            )

        return NextSuggestion(
            sourceType="predefined",
            code="ENTER_PREVIEW",
            title="进入预览",
            description="范围结论已存在，可以进入预览阶段。",
            action={
                "kind": "navigate",
                "route": f"/projects/{project_id}/preview",
            },
        )
