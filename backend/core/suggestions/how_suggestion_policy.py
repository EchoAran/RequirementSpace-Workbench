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
        public_project_id: str | None = None,
    ) -> NextSuggestion:
        context = await load_issue_project_context(
            project_id=project_id,
            session=session,
        )
        pub_id = public_project_id or str(project_id)

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
                        "project_id": pub_id,
                    },
                },
            )

        # Non-equilibrium: all flows exist but none have steps.
        # Instead of suggesting ENTER_SCOPE, guide the user to complete flow steps.
        flows_with_steps = [flow for flow in context.flows if flow.steps]
        if context.flows and not flows_with_steps:
            return NextSuggestion(
                sourceType="predefined",
                code="COMPLETE_FLOW_STEPS",
                title="完善流程步骤",
                description="当前流程尚未包含可执行步骤，建议先补充流程步骤再进入 Scope。",
                target={
                    "type": "flow",
                    "id": context.flows[0].flow_id,
                },
                action={
                    "kind": "open_panel",
                    "route": f"/projects/{pub_id}/how",
                    "panel": "flow_editor",
                    "payload": {
                        "flow_id": context.flows[0].flow_id,
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
                "kind": "stage_transition",
                "transition_action": "enter_scope",
                "route": f"/projects/{pub_id}/scope",
            },
        )
