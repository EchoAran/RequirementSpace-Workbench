"""
Baseline Version Migration Service.
负责将已有项目数据安全、无痛地初始化为版本控制模式。
"""
import logging
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.logging.events import (
    VC_MIGRATION_COMPLETED,
    VC_MIGRATION_FAILED,
    VC_MIGRATION_PROJECT_COMPLETED,
    VC_MIGRATION_PROJECT_FAILED,
    VC_MIGRATION_PROJECT_SKIPPED,
    VC_MIGRATION_STARTED,
)
from backend.core.logging.logger import get_logger, log_event

logger = get_logger("backend.version_control.baseline_migration")
MIGRATION_CATEGORY = "domain"

from backend.api.modules.version_control.application.migration_backfill import (
    _backfill_actors,
    _backfill_business_objects,
    _backfill_choice_groups,
    _backfill_features_and_relations,
    _backfill_flows,
    _backfill_scenarios,
    _backfill_scopes,
    _has_table,
)
from backend.api.modules.version_control.domain.serializer import (
    compute_state_hash,
    serialize_requirement_space,
    to_deterministic_json,
)
from backend.database.model import (
    BranchWorkspaceModel,
    ProjectModel,
    RequirementBranchModel,
    RequirementCommitModel,
    UserModel,
)

TARGET_TABLES = [
    "actors",
    "features",
    "feature_relations",
    "feature_scopes",
    "scenarios",
    "scenario_acceptance_criteria",
    "business_objects",
    "business_object_attributes",
    "flows",
    "flow_steps",
    "choice_groups",
    "choices",
]


def _create_main_branch_and_workspace(
    db: Session,
    project: ProjectModel,
    head_commit_id: int | None = None,
) -> tuple[RequirementBranchModel, BranchWorkspaceModel]:
    """创建主分支 main 及对应的 BranchWorkspace 实体。"""
    db.add(project)
    db.flush()
    creator_id = project.owner_user_id
    if creator_id is not None and _has_table(db, "users"):
        user_exists = db.scalars(select(UserModel.id).where(UserModel.id == creator_id)).first()
        if not user_exists:
            creator_id = None
    main_branch = RequirementBranchModel(
        project=project,
        name="main",
        description="Default protected branch for formal requirement model evolution",
        head_commit_id=head_commit_id,
        source_commit_id=head_commit_id,
        is_protected=True,
        is_default=True,
        created_by_user_id=creator_id,
        status="active",
    )
    db.add(main_branch)
    db.flush()

    main_workspace = BranchWorkspaceModel(
        project_id=project.id,
        branch_id=main_branch.id,
        user_requirements=project.user_requirements or "",
        kano_status=project.kano_status or "missing",
        unlocked_stages=project.unlocked_stages or "",
    )
    db.add(main_workspace)
    db.flush()

    return main_branch, main_workspace


def _create_baseline_commit(
    db: Session,
    project: ProjectModel,
    raw_workspace_dict: dict[str, Any],
) -> RequirementCommitModel:
    """序列化规范化需求空间图谱，计算哈希并持久化首个基线 Commit。"""
    normalized_model = serialize_requirement_space(raw_workspace_dict)
    state_json = to_deterministic_json(normalized_model)
    state_hash = compute_state_hash(state_json)

    summary = {
        "actor_count": len(raw_workspace_dict["actors"]),
        "feature_count": len(raw_workspace_dict["features"]),
        "scenario_count": len(raw_workspace_dict["scenarios"]),
        "business_object_count": len(raw_workspace_dict["business_objects"]),
        "flow_count": len(raw_workspace_dict["flows"]),
        "scope_count": len(raw_workspace_dict["scopes"]),
    }

    creator_id = project.owner_user_id
    if creator_id is not None and _has_table(db, "users"):
        user_exists = db.scalars(select(UserModel.id).where(UserModel.id == creator_id)).first()
        if not user_exists:
            creator_id = None

    commit = RequirementCommitModel(
        project_id=project.id,
        message="Initial baseline commit created during version control migration",
        state_json=state_json,
        state_hash=state_hash,
        schema_version="1.0",
        author_user_id=creator_id,
        summary_json=summary,
    )
    db.add(commit)
    db.flush()

    return commit


def migrate_project_to_version_control(
    db: Session,
    project: ProjectModel,
) -> dict[str, Any]:
    """
    针对单个项目执行版本控制基线初始化迁移（主控制流）。
    """
    if project not in db:
        db.add(project)
    db.flush()
    if not _has_table(db, "requirement_branches"):
        return {"status": "skipped", "reason": "requirement_branches table not yet present"}

    existing_main = db.scalars(
        select(RequirementBranchModel).where(
            RequirementBranchModel.project_id == project.id,
            RequirementBranchModel.name == "main",
        )
    ).first()

    if existing_main:
        workspace = db.scalars(
            select(BranchWorkspaceModel).where(
                BranchWorkspaceModel.project_id == project.id,
                BranchWorkspaceModel.branch_id == existing_main.id
            )
        ).first()
        if workspace:
            workspace.user_requirements = project.user_requirements or ""
            workspace.kano_status = project.kano_status or "missing"
            workspace.unlocked_stages = project.unlocked_stages or ""

            _backfill_actors(db, project.id, workspace.id)
            _, _, feat_map = _backfill_features_and_relations(db, project.id, workspace.id)
            _backfill_scenarios(db, project.id, workspace.id, feat_map)
            _, bo_map = _backfill_business_objects(db, project.id, workspace.id)
            _backfill_flows(db, project.id, workspace.id, feat_map, bo_map)
            _backfill_scopes(db, project.id, workspace.id, feat_map)
            _backfill_choice_groups(db, project.id, workspace.id)
            db.flush()
        log_event(
            logger,
            logging.INFO,
            MIGRATION_CATEGORY,
            VC_MIGRATION_PROJECT_SKIPPED,
            "Project already migrated; repeatable backfill completed",
            project_id=project.id,
            main_branch_public_id=existing_main.public_id,
        )
        return {
            "status": "skipped",
            "message": f"Project {project.id} already has a main branch. Repeatable backfill completed.",
            "project_id": project.id,
            "main_branch_public_id": existing_main.public_id,
            "head_commit_id": existing_main.head_commit_id,
        }

    # 1. 创建主分支与工作区（获得真实 workspace.id）
    main_branch, workspace = _create_main_branch_and_workspace(db, project, head_commit_id=None)

    # 2. 用真实 workspace.id 填充实体并获得规范图谱字典
    actor_dicts = _backfill_actors(db, project.id, workspace.id)
    feat_dicts, rel_dicts, feat_map = _backfill_features_and_relations(db, project.id, workspace.id)
    sc_dicts = _backfill_scenarios(db, project.id, workspace.id, feat_map)
    bo_dicts, bo_map = _backfill_business_objects(db, project.id, workspace.id)
    flow_dicts = _backfill_flows(db, project.id, workspace.id, feat_map, bo_map)
    scope_dicts = _backfill_scopes(db, project.id, workspace.id, feat_map)
    _backfill_choice_groups(db, project.id, workspace.id)

    db.flush()

    raw_workspace_dict = {
        "project_metadata": {
            "user_requirements": project.user_requirements or "",
            "kano_status": project.kano_status or "missing",
            "unlocked_stages": project.unlocked_stages or "",
        },
        "actors": actor_dicts,
        "features": feat_dicts,
        "feature_relations": rel_dicts,
        "scenarios": sc_dicts,
        "business_objects": bo_dicts,
        "flows": flow_dicts,
        "scopes": scope_dicts,
    }

    # 3. 创建首个基线 Commit 并将 commit.id 更新到 main_branch
    commit = _create_baseline_commit(db, project, raw_workspace_dict)
    main_branch.head_commit_id = commit.id
    main_branch.source_commit_id = commit.id

    db.flush()

    log_event(
        logger,
        logging.INFO,
        MIGRATION_CATEGORY,
        VC_MIGRATION_PROJECT_COMPLETED,
        "Baseline version created",
        project_id=project.id,
        main_branch_public_id=main_branch.public_id,
        head_commit_public_id=commit.public_id,
        summary=commit.summary_json,
    )

    return {
        "status": "success",
        "message": "Baseline version created successfully",
        "project_id": project.id,
        "main_branch_public_id": main_branch.public_id,
        "head_commit_public_id": commit.public_id,
        "state_hash": commit.state_hash,
        "summary": commit.summary_json,
    }


def migrate_all_projects_to_version_control(db: Session) -> list[dict[str, Any]]:
    """
    遍历系统中所有 Project，批量执行版本控制基线迁移。
    使用 Savepoint 隔离每个项目的迁移，若任何项目迁移失败则回滚该项目变更并抛出异常，
    确保基线迁移的原子性与可靠性。
    """
    if not _has_table(db, "projects"):
        return []
    projects = db.scalars(select(ProjectModel)).all()
    started = time.perf_counter()
    log_event(
        logger,
        logging.INFO,
        MIGRATION_CATEGORY,
        VC_MIGRATION_STARTED,
        "Version control baseline migration started",
        project_count=len(projects),
    )
    results = []
    failed_projects = []
    for project in projects:
        try:
            with db.begin_nested():
                result = migrate_project_to_version_control(db, project)
                if result.get("status") == "failed":
                    raise RuntimeError(result.get("error", "Unknown project baseline migration error"))
                results.append(result)
        except Exception as ex:
            failed_projects.append((project.id, str(ex)))
            log_event(
                logger,
                logging.WARNING,
                MIGRATION_CATEGORY,
                VC_MIGRATION_PROJECT_FAILED,
                "Project baseline migration failed",
                project_id=project.id,
                error_type=type(ex).__name__,
            )
            results.append({
                "status": "failed",
                "project_id": project.id,
                "error": str(ex),
                "message": f"Project {project.id} baseline migration failed: {ex!s}",
            })

    success_count = sum(1 for r in results if r.get("status") == "success")
    skipped_count = sum(1 for r in results if r.get("status") == "skipped")

    if failed_projects:
        fail_details = ", ".join(f"Project {pid}: {err}" for pid, err in failed_projects)
        log_event(
            logger,
            logging.ERROR,
            MIGRATION_CATEGORY,
            VC_MIGRATION_FAILED,
            "Version control baseline migration failed",
            failed_projects=[pid for pid, _ in failed_projects],
            success_count=success_count,
            skipped_count=skipped_count,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
        raise RuntimeError(f"Version control baseline migration failed for project(s): {fail_details}")

    log_event(
        logger,
        logging.INFO,
        MIGRATION_CATEGORY,
        VC_MIGRATION_COMPLETED,
        "Version control baseline migration completed",
        success_count=success_count,
        skipped_count=skipped_count,
        failed_count=0,
        total_projects=len(projects),
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
    db.flush()
    return results
