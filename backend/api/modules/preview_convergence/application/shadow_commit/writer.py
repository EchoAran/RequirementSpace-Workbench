from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.shadow_preview.shadow_patch_validator import (
    ShadowPatchValidator,
)
from backend.database.model import (
    PerceptionJobModel,
    PerceptionSlotModel,
    PreviewShadowDraftModel,
    ProjectModel,
    beijing_now,
)

from ..shadow_project_creator import (
    build_project_snapshot,
    calculate_stable_snapshot_hash,
)
from .common import _CommitIdMaps
from .entity_writer import _write_patch_entities
from .prototype_writer import _copy_prototype_preview
from .scope_writer import _ensure_leaf_scopes, _upsert_scopes


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
    current_snapshot = await build_project_snapshot(project_id, session)
    current_hash = calculate_stable_snapshot_hash(current_snapshot)
    if current_hash != draft.base_snapshot_hash:
        raise ValueError("shadow_draft_conflict")
    ShadowPatchValidator.validate_patch(
        draft.patch_json,
        current_snapshot,
        current_snapshot["project_id"],
    )
    return current_snapshot

async def _finalize_project(
    project_id: int,
    session: AsyncSession,
) -> None:
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
    await session.execute(
        delete(PerceptionSlotModel).where(
            PerceptionSlotModel.project_id == project_id
        )
    )

async def commit_shadow_draft(
    service,
    project_id: int,
    draft_id: str,
    session: AsyncSession,
) -> None:
    prototype_generation_service = service._prototype_generation_service
    draft = await _load_ready_draft(draft_id, session)
    await _validate_draft_base(project_id, draft, session)
    patch = draft.patch_json
    id_maps = _CommitIdMaps()

    await _write_patch_entities(project_id, patch, id_maps, session)
    await _upsert_scopes(patch, id_maps, session)
    await _ensure_leaf_scopes(project_id, session)
    await _finalize_project(project_id, session)
    await _clear_perception_cache(project_id, session)
    draft.status = "committed"
    draft.committed_at = beijing_now()
    await session.flush()
    await _copy_prototype_preview(
        project_id,
        draft,
        patch,
        id_maps,
        prototype_generation_service,
        session,
    )
    await session.commit()
    await prototype_generation_service.generate_preview(
        project_id=project_id,
        force_regenerate=True,
    )
