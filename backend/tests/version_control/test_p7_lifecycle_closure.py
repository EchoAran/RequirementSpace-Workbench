from __future__ import annotations

import copy
import uuid

from sqlalchemy import select

from backend.api.modules.version_control.application.workspace_restoration import (
    copy_workspace,
    restore_workspace_from_state,
    scrub_workspace,
)
from backend.api.modules.version_control.application.workspace_serializer import (
    serialize_workspace,
)
from backend.api.modules.version_control.domain.semantic_diff import (
    compute_semantic_diff,
)
from backend.api.modules.version_control.domain.semantic_merge import (
    compute_three_way_merge,
)
from backend.api.modules.version_control.domain.serializer import (
    serialize_requirement_space,
)
from backend.database.model import (
    BranchWorkspaceModel,
    DomainRuleModel,
    FlowModel,
    FlowStepModel,
    FlowTransitionModel,
    RequirementBranchModel,
    RuleLinkModel,
)


def _logical_uuid() -> str:
    return str(uuid.uuid4())


def _semantic_state() -> dict:
    return serialize_requirement_space({
        "domain_rules": [{
            "logical_uuid": "rule-1",
            "parent_rule_logical_uuid": None,
            "title": "Payment approval",
            "statement": "Payments require approval.",
            "origin": "manual",
            "confirmation_status": "confirmed",
        }],
        "rule_links": [{
            "logical_uuid": "link-1",
            "rule_logical_uuid": "rule-1",
            "target_kind": "flow_transition",
            "target_logical_uuid": "transition-1",
            "link_purpose": "applies_to",
            "context_text": "Successful branch",
        }],
        "flows": [{
            "logical_uuid": "flow-1",
            "name": "Payment",
            "steps": [
                {"logical_uuid": "step-1", "position": 0, "name": "Start"},
                {"logical_uuid": "step-2", "position": 1, "name": "Finish"},
            ],
            "transitions": [{
                "logical_uuid": "transition-1",
                "source_step_logical_uuid": "step-1",
                "target_step_logical_uuid": "step-2",
                "label": "success",
                "condition_text": "payment succeeds",
                "is_default": True,
                "position": 0,
                "semantic_tags": ["payment"],
                "origin": "manual",
                "confirmation_status": "confirmed",
            }],
        }],
    })


def test_rule_and_transition_aggregate_survives_copy_and_restore(
    sync_db_session,
    seeded_vc_project,
):
    source_workspace = seeded_vc_project.main_workspace
    flow = sync_db_session.scalars(
        select(FlowModel).where(FlowModel.workspace_id == source_workspace.id)
    ).one()
    source_step = sync_db_session.scalars(
        select(FlowStepModel).where(FlowStepModel.flow_id == flow.id)
    ).one()
    target_step = FlowStepModel(
        workspace_id=source_workspace.id,
        logical_uuid=_logical_uuid(),
        flow_id=flow.id,
        position=1,
        name="Complete payment",
        description="",
        step_type="systemAction",
        confirmation_status="confirmed",
    )
    sync_db_session.add(target_step)
    sync_db_session.flush()
    transition = FlowTransitionModel(
        workspace_id=source_workspace.id,
        project_id=seeded_vc_project.project.id,
        logical_uuid=_logical_uuid(),
        flow_id=flow.id,
        source_step_id=source_step.id,
        target_step_id=target_step.id,
        label="success",
        condition_text="payment succeeds",
        is_default=True,
        position=0,
        semantic_tags=["success", "payment"],
        origin="manual",
        confirmation_status="confirmed",
    )
    parent_rule = DomainRuleModel(
        workspace_id=source_workspace.id,
        project_id=seeded_vc_project.project.id,
        logical_uuid=_logical_uuid(),
        title="Payment approval",
        statement="Payments require approval.",
        origin="manual",
        confirmation_status="confirmed",
    )
    sync_db_session.add_all([transition, parent_rule])
    sync_db_session.flush()
    child_rule = DomainRuleModel(
        workspace_id=source_workspace.id,
        project_id=seeded_vc_project.project.id,
        logical_uuid=_logical_uuid(),
        parent_rule_id=parent_rule.id,
        title="Successful payment",
        statement="Approved payments proceed on success.",
        origin="flow_refinement",
        confirmation_status="needs_confirmation",
    )
    sync_db_session.add(child_rule)
    sync_db_session.flush()
    sync_db_session.add_all([
        RuleLinkModel(
            workspace_id=source_workspace.id,
            project_id=seeded_vc_project.project.id,
            logical_uuid=_logical_uuid(),
            rule_id=child_rule.id,
            target_kind="flow_transition",
            target_logical_uuid=transition.logical_uuid,
            link_purpose="applies_to",
            context_text="Successful branch",
        ),
    ])
    sync_db_session.flush()

    source_state = serialize_workspace(sync_db_session, source_workspace)
    target_branch = RequirementBranchModel(
        project_id=seeded_vc_project.project.id,
        name="p7-copy",
        head_commit_id=seeded_vc_project.main_branch.head_commit_id,
        source_commit_id=seeded_vc_project.main_branch.head_commit_id,
        created_by_user_id=seeded_vc_project.user.id,
    )
    sync_db_session.add(target_branch)
    sync_db_session.flush()
    target_workspace = BranchWorkspaceModel(
        project_id=seeded_vc_project.project.id,
        branch_id=target_branch.id,
    )
    sync_db_session.add(target_workspace)
    sync_db_session.flush()

    copy_workspace(sync_db_session, source_workspace, target_workspace)
    copied_state = serialize_workspace(sync_db_session, target_workspace)
    assert copied_state == source_state

    scrub_workspace(sync_db_session, target_workspace.id)
    restore_workspace_from_state(sync_db_session, target_workspace, source_state)
    restored_state = serialize_workspace(sync_db_session, target_workspace)
    assert restored_state == source_state


def test_semantic_diff_reports_rule_and_transition_changes():
    base = _semantic_state()
    target = copy.deepcopy(base)
    target["domain_rules"][0]["statement"] = "Approved payments may proceed."
    target["flows"][0]["transitions"][0]["condition_text"] = "approval succeeds"

    entries = compute_semantic_diff(base, target)["entries"]

    assert any(
        entry["entity_type"] == "domain_rule"
        and entry.get("field") == "statement"
        for entry in entries
    )
    assert any(
        entry["entity_type"] == "flow_transition"
        and entry.get("field") == "condition_text"
        for entry in entries
    )


def test_semantic_diff_reports_derived_path_projection_changes():
    base = _semantic_state()
    target = copy.deepcopy(base)
    target["flows"][0]["steps"].append(
        {
            "logical_uuid": "step-3",
            "position": 2,
            "name": "Alternative finish",
            "description": "",
            "step_type": "task",
            "confirmation_status": "confirmed",
            "actor_logical_uuids": [],
            "input_business_object_logical_uuids": [],
            "output_business_object_logical_uuids": [],
        }
    )
    target["flows"][0]["transitions"].append(
        {
            "logical_uuid": "transition-2",
            "source_step_logical_uuid": "step-1",
            "target_step_logical_uuid": "step-3",
            "label": "alternative",
            "condition_text": "payment needs review",
            "is_default": False,
            "position": 1,
            "semantic_tags": [],
            "origin": "manual",
            "confirmation_status": "confirmed",
        }
    )

    entries = compute_semantic_diff(base, target)["entries"]

    path_entry = next(
        entry for entry in entries if entry["entity_type"] == "path_projection"
    )
    assert path_entry["entity_uuid"] == "flow-1"
    assert path_entry["before"] != path_entry["after"]


def test_semantic_merge_exposes_rule_and_transition_conflicts():
    base = _semantic_state()
    target = copy.deepcopy(base)
    source = copy.deepcopy(base)
    target["domain_rules"][0]["statement"] = "Target rule statement"
    source["domain_rules"][0]["statement"] = "Source rule statement"
    target["flows"][0]["transitions"][0]["condition_text"] = "target condition"
    source["flows"][0]["transitions"][0]["condition_text"] = "source condition"

    result = compute_three_way_merge(base, target, source)

    assert any(
        conflict["entity_type"] == "domain_rule"
        and conflict["path"] == "statement"
        for conflict in result["conflicts"]
    )
    assert any(
        conflict["entity_type"] == "flow_transition"
        and conflict["path"] == "condition_text"
        for conflict in result["conflicts"]
    )
