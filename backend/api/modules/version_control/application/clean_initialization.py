"""Create the initial version-control workspace for a new project."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.api.modules.version_control.application.workspace_serializer import (
    serialize_workspace,
)
from backend.api.modules.version_control.domain.serializer import (
    CURRENT_SCHEMA_VERSION,
    compute_state_hash,
    to_deterministic_json,
)
from backend.database.model import (
    ActorModel,
    BranchWorkspaceModel,
    BusinessObjectModel,
    DomainRuleModel,
    FeatureModel,
    FlowModel,
    ProjectModel,
    RequirementBranchModel,
    RequirementCommitModel,
    ScenarioModel,
    ScopeModel,
)

_PROJECT_ENTITY_MODELS = (
    ActorModel,
    FeatureModel,
    ScenarioModel,
    BusinessObjectModel,
    FlowModel,
    DomainRuleModel,
)


def _ensure_clean_project(db: Session, project_id: int) -> None:
    """Reject initialization when version or requirement-space data already exists."""
    existing_branch = db.scalar(
        select(RequirementBranchModel.id).where(
            RequirementBranchModel.project_id == project_id
        ).limit(1)
    )
    existing_workspace = db.scalar(
        select(BranchWorkspaceModel.id).where(
            BranchWorkspaceModel.project_id == project_id
        ).limit(1)
    )
    existing_commit = db.scalar(
        select(RequirementCommitModel.id).where(
            RequirementCommitModel.project_id == project_id
        ).limit(1)
    )
    if existing_branch or existing_workspace or existing_commit:
        raise ValueError("project_version_control_already_initialized")

    for model in _PROJECT_ENTITY_MODELS:
        if db.scalar(select(func.count()).select_from(model).where(model.project_id == project_id)):
            raise ValueError("clean_initialization_requires_empty_project")
    scope_count = db.scalar(
        select(func.count())
        .select_from(ScopeModel)
        .join(FeatureModel, ScopeModel.feature_id == FeatureModel.id)
        .where(FeatureModel.project_id == project_id)
    )
    if scope_count:
        raise ValueError("clean_initialization_requires_empty_project")


def create_initial_workspace(
    db: Session,
    project: ProjectModel,
) -> tuple[RequirementBranchModel, BranchWorkspaceModel]:
    """Create the protected main branch and empty workspace for a new project."""
    if project.id is None:
        db.add(project)
        db.flush()
    _ensure_clean_project(db, project.id)

    branch = RequirementBranchModel(
        project_id=project.id,
        name="main",
        description="Default protected branch for formal requirement model evolution",
        is_protected=True,
        is_default=True,
        created_by_user_id=project.owner_user_id,
        status="active",
    )
    db.add(branch)
    db.flush()

    workspace = BranchWorkspaceModel(
        project_id=project.id,
        branch_id=branch.id,
        user_requirements=project.user_requirements or "",
        kano_status=project.kano_status or "missing",
        unlocked_stages=project.unlocked_stages or "",
    )
    db.add(workspace)
    db.flush()
    return branch, workspace


def finalize_initial_commit(
    db: Session,
    project: ProjectModel,
    branch: RequirementBranchModel,
    workspace: BranchWorkspaceModel,
) -> RequirementCommitModel:
    """Serialize the populated workspace into the project's first immutable commit."""
    if branch.head_commit_id is not None:
        raise ValueError("initial_commit_already_created")

    state = serialize_workspace(db, workspace)
    state_json = to_deterministic_json(state)
    commit = RequirementCommitModel(
        project_id=project.id,
        message="Initial baseline commit",
        state_json=state_json,
        state_hash=compute_state_hash(state_json),
        schema_version=CURRENT_SCHEMA_VERSION,
        author_user_id=project.owner_user_id,
        summary_json=_build_initial_summary(state),
    )
    db.add(commit)
    db.flush()
    branch.head_commit_id = commit.id
    branch.source_commit_id = commit.id
    db.flush()
    return commit


def initialize_project_version_control(
    db: Session,
    project: ProjectModel,
) -> dict[str, Any]:
    """Initialize an empty new project with one workspace and one schema-current commit."""
    branch, workspace = create_initial_workspace(db, project)
    commit = finalize_initial_commit(db, project, branch, workspace)
    return {
        "status": "success",
        "project_id": project.id,
        "main_branch_public_id": branch.public_id,
        "head_commit_id": commit.id,
    }


def _build_initial_summary(state: dict[str, Any]) -> dict[str, int]:
    """Count the top-level entities represented by the initial commit."""
    return {
        "actor_count": len(state.get("actors", [])),
        "feature_count": len(state.get("features", [])),
        "scenario_count": len(state.get("scenarios", [])),
        "business_object_count": len(state.get("business_objects", [])),
        "flow_count": len(state.get("flows", [])),
        "scope_count": len(state.get("scopes", [])),
        "domain_rule_count": len(state.get("domain_rules", [])),
        "rule_link_count": len(state.get("rule_links", [])),
    }
