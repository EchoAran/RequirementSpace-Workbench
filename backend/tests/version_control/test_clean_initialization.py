"""Tests for clean project version-control initialization."""

import json

import pytest
from sqlalchemy import select

from backend.api.modules.version_control.application.clean_initialization import (
    create_initial_workspace,
    finalize_initial_commit,
    initialize_project_version_control,
)
from backend.api.modules.version_control.domain.serializer import CURRENT_SCHEMA_VERSION
from backend.database.model import (
    ActorModel,
    BranchWorkspaceModel,
    RequirementBranchModel,
    RequirementCommitModel,
)


def test_empty_project_initializes_current_schema(sync_db_session, seeded_project):
    result = initialize_project_version_control(sync_db_session, seeded_project)

    branch = sync_db_session.scalar(
        select(RequirementBranchModel).where(
            RequirementBranchModel.project_id == seeded_project.id
        )
    )
    workspace = sync_db_session.scalar(
        select(BranchWorkspaceModel).where(
            BranchWorkspaceModel.project_id == seeded_project.id
        )
    )
    commit = sync_db_session.get(RequirementCommitModel, branch.head_commit_id)

    assert result["status"] == "success"
    assert workspace.branch_id == branch.id
    assert commit.schema_version == CURRENT_SCHEMA_VERSION
    assert json.loads(commit.state_json)["schema_version"] == CURRENT_SCHEMA_VERSION


def test_initialization_rejects_existing_requirement_data(sync_db_session, seeded_project):
    sync_db_session.add(
        ActorModel(project_id=seeded_project.id, name="Existing actor", description="")
    )
    sync_db_session.flush()

    with pytest.raises(ValueError, match="clean_initialization_requires_empty_project"):
        initialize_project_version_control(sync_db_session, seeded_project)


def test_initialization_rejects_second_workspace(sync_db_session, seeded_project):
    initialize_project_version_control(sync_db_session, seeded_project)

    with pytest.raises(ValueError, match="project_version_control_already_initialized"):
        initialize_project_version_control(sync_db_session, seeded_project)


def test_initial_commit_captures_entities_created_in_workspace(
    sync_db_session,
    seeded_project,
):
    branch, workspace = create_initial_workspace(sync_db_session, seeded_project)
    actor = ActorModel(
        project_id=seeded_project.id,
        workspace_id=workspace.id,
        name="Buyer",
        description="",
    )
    sync_db_session.add(actor)
    sync_db_session.flush()

    commit = finalize_initial_commit(
        sync_db_session,
        seeded_project,
        branch,
        workspace,
    )
    state = json.loads(commit.state_json)

    assert [item["logical_uuid"] for item in state["actors"]] == [actor.logical_uuid]
    assert commit.summary_json["actor_count"] == 1
