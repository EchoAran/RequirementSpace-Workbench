from backend.core.detectors.issue_context_loader import (
    load_issue_project_context,
)
from backend.core.suggestions.stage_suggestion_policy import (
    StageSuggestionPolicy,
)
from backend.schemas import NextSuggestion


class HowSuggestionPolicy(StageSuggestionPolicy):
    async def get_next(
        self,
        project_id: int,
        session,
    ) -> NextSuggestion:
        context = await load_issue_project_context(
            project_id=project_id,
            session=session,
        )

        if not context.flows or not context.business_objects:
            return NextSuggestion(
                sourceType="generator",
                code="GENERATE_FLOWS_AND_BUSINESS_OBJECTS",
                title="生成流程与业务对象",
                description="当前项目还没有完整流程与业务对象，建议先生成草稿。",
                action={
                    "kind": "create_draft",
                    "draft_type": "flow_generation",
                    "endpoint": "/api/flow_generation_drafts",
                    "payload": {
                        "project_id": project_id,
                    },
                },
            )

        # Flow perception is orchestrated by NextSuggestionService after this
        # base policy says How has enough draft material to enter Scope.
        return NextSuggestion(
            sourceType="predefined",
            code="ENTER_SCOPE",
            title="进入 Scope 阶段",
            description="How 阶段已有流程和业务对象，可以继续判断功能范围。",
            action={
                "kind": "navigate",
                "route": f"/projects/{project_id}/scope",
            },
        )
