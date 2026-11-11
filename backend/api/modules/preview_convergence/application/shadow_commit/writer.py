from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logging.events import SHADOW_APPLY_MISMATCH
from backend.core.observability import emit_how_lifecycle_event
from backend.core.shadow_preview.shadow_patch_validator import (
    ShadowPatchValidator,
)
from backend.database.model import (
    BranchWorkspaceModel,
    PerceptionJobModel,
    PreviewShadowDraftModel,
    ProjectModel,
    RequirementBranchModel,
    beijing_now,
)

from ..shadow_patch_applier import PreviewShadowPatchApplier
from ..shadow_project_creator import (
    build_project_snapshot,
    calculate_stable_snapshot_hash,
)
from .common import _CommitIdMaps
from .entity_writer import _write_patch_entities
from .equivalence import build_how_semantic_signature
from .prototype_writer import _copy_prototype_preview
from .scope_writer import _upsert_scopes


async def _load_ready_draft(
    draft_id: str,
    session: AsyncSession,
) -> PreviewShadowDraftModel:
    result = await session.execute(
        select(PreviewShadowDraftModel).where(
            PreviewShadowDraftModel.draft_id == draft_id
        )
    )
    draft = result.scalar_one_or_none()
    if not draft:
        raise ValueError("shadow_draft_not_found")
    if draft.status != "ready":
        raise ValueError("shadow_draft_not_ready")
    return draft

async def _validate_draft_base(
    project_id: int,
    draft: PreviewShadowDraftModel,
    session: AsyncSession,
) -> dict:
    workspace_id = draft.workspace_id
    if workspace_id is None:
        raise ValueError("shadow_draft_missing_workspace")
    current_snapshot = await build_project_snapshot(project_id, workspace_id, session)
    current_hash = calculate_stable_snapshot_hash(current_snapshot)
    if current_hash != draft.base_snapshot_hash:
        raise ValueError("shadow_draft_conflict")
    ShadowPatchValidator.validate_patch(
        draft.patch_json,
        current_snapshot,
        current_snapshot["project_id"],
    )
    expected_snapshot, _ = PreviewShadowPatchApplier.apply_patch_to_snapshot(
        current_snapshot,
        draft.patch_json,
    )
    return expected_snapshot

async def _finalize_project(
    project_id: int,
    workspace_id: int,
    session: AsyncSession,
) -> None:
    workspace = await session.get(BranchWorkspaceModel, workspace_id)
    if workspace is not None:
        workspace.kano_status = "generated"
        workspace.unlocked_stages = "what,how,scope"
    project = await session.get(ProjectModel, project_id)
    if not project:
        return
    if project.kano_status not in ("generated", "skipped"):
        project.kano_status = "generated"
    project.unlocked_stages = "what,how,scope"

async def _clear_perception_cache(
    project_id: int,
    session: AsyncSession,
) -> None:
    await session.execute(
        delete(PerceptionJobModel).where(
            PerceptionJobModel.project_id == project_id,
            PerceptionJobModel.stage.in_(["what", "how", "scope"]),
        )
    )


async def _resolve_branch_ref(
    workspace_id: int,
    session: AsyncSession,
) -> str | None:
    workspace = await session.get(BranchWorkspaceModel, workspace_id)
    if workspace is None:
        return None
    branch = await session.get(RequirementBranchModel, workspace.branch_id)
    return branch.public_id if branch else None


async def commit_shadow_draft(
    service,
    project_id: int,
    draft_id: str,
    session: AsyncSession,
) -> None:
    prototype_generation_service = service._prototype_generation_service
    draft = await _load_ready_draft(draft_id, session)
    workspace_id = draft.workspace_id
    if workspace_id is None:
        raise ValueError("shadow_draft_missing_workspace")
    branch_ref = await _resolve_branch_ref(workspace_id, session)
    expected_snapshot = await _validate_draft_base(project_id, draft, session)
    patch = draft.patch_json
    id_maps = _CommitIdMaps()

    savepoint = await session.begin_nested()
    try:
        await _write_patch_entities(project_id, workspace_id, patch, id_maps, session)
        await _upsert_scopes(workspace_id, patch, id_maps, session)
        await _finalize_project(project_id, workspace_id, session)
        await _clear_perception_cache(project_id, session)
        await session.flush()
        persisted_snapshot = await build_project_snapshot(
            project_id, workspace_id, session
        )
        if build_how_semantic_signature(
            expected_snapshot
        ) != build_how_semantic_signature(persisted_snapshot):
            emit_how_lifecycle_event(
                SHADOW_APPLY_MISMATCH,
                capability="shadow_commit",
                project_id=project_id,
                error_code="shadow_apply_mismatch",
            )
            raise ValueError("shadow_apply_mismatch")
        draft.status = "committed"
        draft.committed_at = beijing_now()
        await _copy_prototype_preview(
            project_id,
            workspace_id,
            draft,
            patch,
            id_maps,
            prototype_generation_service,
            session,
        )
        await savepoint.commit()
    except Exception:
        if savepoint.is_active:
            await savepoint.rollback()
        raise
    await session.commit()
    await prototype_generation_service.generate_preview(
        project_id=project_id,
        force_regenerate=True,
        branch_ref=branch_ref,
    )
