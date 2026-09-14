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
        "INVALID_STEP_ACTOR": {
            "title": "修复步骤参与者",
            "description": "部分流程步骤关联了无效或已删除的角色，请重新关联有效参与者。",
            "stage": "how",
            "route_pattern": "/projects/{project_id}/how/flow-steps/{target_id}",
            "panel": "flow_step_actor_relation",
        },
        "INVALID_STEP_BUSINESS_OBJECT": {
            "title": "修复步骤业务对象",
            "description": "部分流程步骤关联了无效或已删除的业务对象，请重新关联有效业务对象。",
            "stage": "how",
            "route_pattern": "/projects/{project_id}/how/flow-steps/{target_id}",
            "panel": "flow_step_object_relation",
        },
        "JUDGMENT_STEP_WITH_TOO_FEW_BRANCHES": {
            "title": "补充分支",
            "description": "请为判断步骤补充后继分支。",
            "stage": "how",
            "route_pattern": "/projects/{project_id}/how/flow-steps/{target_id}",
            "panel": "flow_transition_relation",
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
        "DOMAIN_RULE_REQUIRED": {
            "title": "添加业务规则",
            "description": "业务流程必须依赖至少一条业务规则。",
            "stage": "how",
            "route_pattern": "/projects/{project_id}/how/rules",
            "panel": "domain_rule",
        },
        "RULE_WITHOUT_SOURCE": {
            "title": "关联需求来源",
            "description": "请为该规则关联对应的需求、场景或验收标准。",
            "stage": "how",
            "route_pattern": "/projects/{project_id}/how/rules/{target_id}",
            "panel": "domain_rule",
        },
        "RULE_NOT_APPLIED": {
            "title": "应用规则至流程",
            "description": "请将该规则关联至对应的流程、步骤或分支跳转。",
            "stage": "how",
            "route_pattern": "/projects/{project_id}/how/rules/{target_id}",
            "panel": "domain_rule",
        },
        "FLOW_USES_UNCONFIRMED_RULE": {
            "title": "确认引用规则",
            "description": "请确认流程所引用的业务规则。",
            "stage": "how",
            "route_pattern": "/projects/{project_id}/how/rules",
            "panel": "rule_confirmation",
        },
        "FLOW_ENTRY_AMBIGUOUS": {
            "title": "调整流程入口",
            "description": "请为流程指定唯一的起始步骤。",
            "stage": "how",
            "route_pattern": "/projects/{project_id}/how/flows/{flow_id}",
            "panel": "flow_editor",
        },
        "FLOW_WITHOUT_ENTRY": {
            "title": "设置起始步骤",
            "description": "流程存在闭环且缺少明确入口步骤，请设置起始步骤。",
            "stage": "how",
            "route_pattern": "/projects/{project_id}/how/flows/{flow_id}",
            "panel": "flow_editor",
        },
        "BRANCH_WITHOUT_EXPLANATION": {
            "title": "补充跳转条件说明",
            "description": "请为分支跳转补充条件说明或关联业务规则。",
            "stage": "how",
            "route_pattern": "/projects/{project_id}/how/flows/{flow_id}",
            "panel": "flow_transition_panel",
        },
        "BRANCH_WITHOUT_DEFAULT": {
            "title": "设置默认流向",
            "description": "请为多出口步骤设置默认流向分支。",
            "stage": "how",
            "route_pattern": "/projects/{project_id}/how/flows/{flow_id}",
            "panel": "flow_transition_panel",
        },
        "TRANSITION_RULE_STALE": {
            "title": "修复跳转规则引用",
            "description": "分支跳转引用的规则已失效或删除，请更新或解除关联。",
            "stage": "how",
            "route_pattern": "/projects/{project_id}/how/flows/{flow_id}",
            "panel": "flow_transition_panel",
        },
        "FLOW_PATH_TRUNCATED": {
            "title": "简化流程拓扑",
            "description": "流程路径分支过多超过计算上限，请拆分或简化子流程。",
            "stage": "how",
            "route_pattern": "/projects/{project_id}/how/flows/{flow_id}",
            "panel": "flow_editor",
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
