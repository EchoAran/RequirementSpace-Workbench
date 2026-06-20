from backend.core.issue_resolution.base_solver import (
    BaseIssueSolver,
)
from backend.schemas import IssueResolution, IssueTarget


class OpenPanelIssueSolver(BaseIssueSolver):
    _action_map = {
        "ACTOR_WITHOUT_FEATURE": {
            "title": "关联功能",
            "description": "请为该角色关联至少一个功能。",
            "stage": "what",
            "route_pattern": "/projects/{project_id}/what/actors/{target_id}",
            "panel": "actor_feature_relation",
        },
        "LEAF_FEATURE_WITHOUT_ACTOR": {
            "title": "关联参与者",
            "description": "请为该叶子功能关联至少一个参与者。",
            "stage": "what",
            "route_pattern": "/projects/{project_id}/what/features/{target_id}",
            "panel": "feature_actor_relation",
        },
        "SCENARIO_ACTOR_NOT_IN_FEATURE_ACTORS": {
            "title": "修正场景关系",
            "description": "请修正场景引用的功能与参与者关系。",
            "stage": "what",
            "route_pattern": "/projects/{project_id}/what/scenarios/{target_id}",
            "panel": "scenario_relation",
        },
        "DUPLICATE_SCENARIO_NAME": {
            "title": "合并重复场景",
            "description": "请检查并合并重复场景。",
            "stage": "what",
            "route_pattern": "/projects/{project_id}/what/scenarios",
            "panel": "scenario_merge",
        },
        "LEAF_FEATURE_WITHOUT_FLOW": {
            "title": "关联流程与功能",
            "description": "请检查流程与功能之间的覆盖关系。",
            "stage": "how",
            "route_pattern": "/projects/{project_id}/how/flows",
            "panel": "flow_feature_relation",
        },
        "FLOW_WITHOUT_FEATURE": {
            "title": "关联流程与功能",
            "description": "请为该流程关联至少一个功能。",
            "stage": "how",
            "route_pattern": "/projects/{project_id}/how/flows",
            "panel": "flow_feature_relation",
        },
        "FLOW_WITHOUT_STEPS": {
            "title": "编辑流程",
            "description": "请打开流程编辑器补充流程步骤。",
            "stage": "how",
            "route_pattern": "/projects/{project_id}/how/flows/{flow_id}",
            "panel": "flow_editor",
        },
        "ACTOR_ACTION_STEP_WITHOUT_ACTOR": {
            "title": "关联步骤参与者",
            "description": "请为用户动作步骤关联参与者。",
            "stage": "how",
            "route_pattern": "/projects/{project_id}/how/flow-steps/{target_id}",
            "panel": "flow_step_actor_relation",
        },
        "JUDGMENT_STEP_WITH_TOO_FEW_BRANCHES": {
            "title": "补充分支",
            "description": "请为判断步骤补充后继分支。",
            "stage": "how",
            "route_pattern": "/projects/{project_id}/how/flow-steps/{target_id}",
            "panel": "flow_step_next_relation",
        },
        "UNREACHABLE_FLOW_STEP": {
            "title": "编辑流程",
            "description": "请打开流程编辑器检查流程结构。",
            "stage": "how",
            "route_pattern": "/projects/{project_id}/how/flows/{flow_id}",
            "panel": "flow_editor",
        },
        "BUSINESS_OBJECT_WITHOUT_USAGE": {
            "title": "检查业务对象使用",
            "description": "请检查该业务对象是否应被流程步骤使用。",
            "stage": "how",
            "route_pattern": (
                "/projects/{project_id}/how/business-objects/{target_id}"
            ),
            "panel": "business_object_usage",
        },
        "BUSINESS_OBJECT_WITHOUT_ATTRIBUTES": {
            "title": "补充业务对象属性",
            "description": "请为该业务对象补充属性。",
            "stage": "how",
            "route_pattern": (
                "/projects/{project_id}/how/business-objects/{target_id}"
            ),
            "panel": "business_object_attributes",
        },
        "SCOPE_WITHOUT_REASON": {
            "title": "补充范围理由",
            "description": "请补充该范围结论的说明理由。",
            "stage": "scope",
            "route_pattern": "/projects/{project_id}/scope/{target_id}",
            "panel": "scope_reason",
        },
    }

    async def resolve(
        self,
        project_id: int,
        issue_code: str,
        target: IssueTarget | None,
        metadata: dict,
        session,
    ) -> IssueResolution:
        config = self._action_map.get(issue_code)

        if config is None:
            raise ValueError("unsupported_issue_code")

        target_id = target.targetId if target is not None else None
        flow_id = metadata.get("flow_id") or target_id

        return IssueResolution(
            issueCode=issue_code,
            resolutionType="open_panel",
            title=config["title"],
            description=config["description"],
            action={
                "kind": "open_panel",
                "route": config["route_pattern"].format(
                    project_id=project_id,
                    target_id=target_id,
                    flow_id=flow_id,
                ),
                "panel": config["panel"],
                "payload": {
                    "target_id": target_id,
                    **metadata,
                },
            },
        )
