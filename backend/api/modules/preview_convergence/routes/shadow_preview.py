from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.llm import get_llm_context
from backend.api.dependencies.ownership import require_owned_project
from backend.api.modules.preview_convergence.application.shadow_convergence import (
    PreviewShadowConvergenceService,
    build_project_snapshot,
    calculate_stable_snapshot_hash,
)
from backend.api.modules.preview_convergence.ports import get_prototype_generation_service
from backend.api.modules.preview_convergence.schemas.prototype import PrototypePreviewResponse
from backend.api.modules.preview_convergence.schemas.shadow_preview import (
    PreviewShadowDraftResponse,
    PreviewShadowRegenerateRequest,
)
from backend.core.llm_context import LLMRequestContext
from backend.database.database import get_session
from backend.database.model import PreviewShadowDraftModel, ProjectModel, UserModel

router = APIRouter(
    prefix="/api/projects/{project_id}/preview-shadow-drafts",
    tags=["preview-shadow"],
)

convergence_service = PreviewShadowConvergenceService()


async def _resolve_shadow_workspace(
    session: AsyncSession,
    project_id: int,
    branch: str | None,
    user_id: int,
    require_write: bool = False,
) -> int:
    from backend.api.modules.version_control.public import map_branch_error, resolve_branch_context

    try:
        _, workspace, permissions = await session.run_sync(
            lambda db: resolve_branch_context(db, project_id, branch, user_id)
        )
    except (ValueError, PermissionError) as error:
        raise map_branch_error(error)
    if require_write and not permissions.get("can_write", False):
        raise HTTPException(status_code=403, detail="Branch is read-only or protected for current user")
    return workspace.id


def _build_draft_response(
    draft: PreviewShadowDraftModel,
    unready_gates: list[str]
) -> PreviewShadowDraftResponse:
    preview_response = None
    if draft.prototype_preview_json:
        preview_response = PrototypePreviewResponse(**draft.prototype_preview_json)

    patch = draft.patch_json or {}
    shadow_summary = {
        "actors": len(patch.get("actors_added", [])),
        "features": len(patch.get("features_added", [])),
        "flows": len(patch.get("flows_added", [])),
        "scopes": len(patch.get("scopes_added", [])),
    }

    # Extract progress information if draft is generating
    current_progress = None
    current_step_label = None
    error_message = draft.error_message

    if draft.status == "generating" and error_message:
        try:
            import json
            data = json.loads(error_message)
            if isinstance(data, dict):
                current_progress = data.get("progress")
                current_step_label = data.get("message")
                error_message = None  # Clear error field for response while generating
        except Exception:
            pass

    return PreviewShadowDraftResponse(
        source="shadow_project",
        draft_id=draft.draft_id,
        status=draft.status,
        unready_gates=unready_gates,
        shadow_summary=shadow_summary,
        prototype_preview=preview_response,
        shadow_snapshot_json=draft.shadow_snapshot_json,
        error_message=error_message,
        current_progress=current_progress,
        current_step_label=current_step_label,
    )


def _unready_gate_names(gates: dict) -> list[str]:
    return [
        stage
        for stage in ("what", "how", "scope")
        if not gates[stage]
    ]


async def _get_or_generate_real_preview(project_id: int, session, branch_ref: str | None = None):
    service = get_prototype_generation_service()
    preview = await service.get_latest_preview(
        project_id=project_id,
        session=session,
        raise_if_missing=False,
        branch_ref=branch_ref,
    )
    if preview is None:
        preview = await service.start_generation(
            project_id=project_id,
            force_regenerate=True,
            branch_ref=branch_ref,
        )
    return preview


async def _find_matching_shadow_draft(
    session,
    *,
    project_id: int,
    workspace_id: int,
    snapshot_hash: str,
):
    result = await session.execute(
        select(PreviewShadowDraftModel)
        .where(
            PreviewShadowDraftModel.project_id == project_id,
            PreviewShadowDraftModel.workspace_id == workspace_id,
            PreviewShadowDraftModel.status.in_(["generating", "ready"]),
            PreviewShadowDraftModel.base_snapshot_hash == snapshot_hash,
        )
        .order_by(PreviewShadowDraftModel.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _mark_active_shadow_drafts_stale(session, project_id: int, workspace_id: int) -> None:
    result = await session.execute(
        select(PreviewShadowDraftModel).where(
            PreviewShadowDraftModel.project_id == project_id,
            PreviewShadowDraftModel.workspace_id == workspace_id,
            PreviewShadowDraftModel.status.in_(["generating", "ready"]),
        )
    )
    for draft in result.scalars().all():
        draft.status = "stale"
        draft.error_message = "stale_by_new_snapshot"
    await session.flush()


async def _create_shadow_draft(
    session,
    *,
    project_id: int,
    workspace_id: int,
    snapshot_hash: str,
    base_snapshot: dict,
) -> PreviewShadowDraftModel:
    draft = PreviewShadowDraftModel(
        project_id=project_id,
        workspace_id=workspace_id,
        draft_id=f"draft_{uuid.uuid4().hex[:12]}",
        status="generating",
        source="shadow_project",
        base_snapshot_hash=snapshot_hash,
        base_snapshot_json=base_snapshot,
    )
    session.add(draft)
    await session.commit()
    return draft


_background_tasks: set[asyncio.Task] = set()


def _start_shadow_convergence(
    project_id: int,
    draft_id: str,
    llm_ctx: LLMRequestContext,
) -> None:
    task = asyncio.create_task(
        convergence_service.converge_shadow_snapshot_task(
            project_id,
            draft_id,
            api_url=llm_ctx.api_url,
            api_key=llm_ctx.api_key,
            model_name=llm_ctx.model_name,
            content_locale=llm_ctx.content_locale,
            content_locale_source=llm_ctx.content_locale_source,
        )
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


@router.post("", response_model=PreviewShadowDraftResponse)
async def prepare_shadow_draft(
    project_id: str,
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    llm_ctx: LLMRequestContext = Depends(get_llm_context),
    owned_project: ProjectModel = Depends(require_owned_project)
):
    """
    Prepare preview draft. If converged, loads or generates real prototype.
    If unconverged, retrieves or spawns shadow convergence.
    """
    ws_id = await _resolve_shadow_workspace(
        session, owned_project.id, branch, user.id, require_write=True
    )

    # Stage gates determine whether convergence is applicable.
    gates = await convergence_service.gate_evaluator.evaluate_gates(
        owned_project.id, session, workspace_id=ws_id
    )
    all_passed = gates["what"] and gates["how"] and gates["scope"]

    if all_passed:
        try:
            preview = await _get_or_generate_real_preview(
                owned_project.id,
                session,
                branch_ref=branch,
            )
            return PreviewShadowDraftResponse(
                source="real_project",
                status=preview.status,
                prototype_preview=preview,
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to generate real preview: {e!s}")

    unready_gates = _unready_gate_names(gates)
    base_snapshot = await build_project_snapshot(owned_project.id, ws_id, session)
    current_hash = calculate_stable_snapshot_hash(base_snapshot)
    existing_draft = await _find_matching_shadow_draft(
        session,
        project_id=owned_project.id,
        workspace_id=ws_id,
        snapshot_hash=current_hash,
    )
    if existing_draft is not None:
        return _build_draft_response(existing_draft, unready_gates)

    await _mark_active_shadow_drafts_stale(session, owned_project.id, ws_id)
    new_draft = await _create_shadow_draft(
        session,
        project_id=owned_project.id,
        workspace_id=ws_id,
        snapshot_hash=current_hash,
        base_snapshot=base_snapshot,
    )
    _start_shadow_convergence(owned_project.id, new_draft.draft_id, llm_ctx)
    return _build_draft_response(new_draft, unready_gates)


@router.get("/active", response_model=PreviewShadowDraftResponse)
async def get_active_shadow_draft(
    project_id: str,
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project)
):
    """
    Get the current active shadow draft for the project if one exists.
    Returns status=idle if no active draft exists.
    """
    ws_id = await _resolve_shadow_workspace(session, owned_project.id, branch, user.id)

    # Stage gates determine whether convergence is applicable.
    gates = await convergence_service.gate_evaluator.evaluate_gates(
        owned_project.id, session, workspace_id=ws_id
    )
    unready_gates = []
    if not gates["what"]:
        unready_gates.append("what")
    if not gates["how"]:
        unready_gates.append("how")
    if not gates["scope"]:
        unready_gates.append("scope")

    # Build base snapshot and hash to match active draft
    base_snapshot = await build_project_snapshot(owned_project.id, ws_id, session)
    current_hash = calculate_stable_snapshot_hash(base_snapshot)

    # An active draft is reusable only for the same snapshot hash.
    existing_res = await session.execute(
        select(PreviewShadowDraftModel)
        .where(
            PreviewShadowDraftModel.project_id == owned_project.id,
            PreviewShadowDraftModel.workspace_id == ws_id,
            PreviewShadowDraftModel.status.in_(["generating", "ready", "failed"]),
            PreviewShadowDraftModel.base_snapshot_hash == current_hash,
        )
        .order_by(PreviewShadowDraftModel.created_at.desc())
        .limit(1)
    )
    existing_draft = existing_res.scalar_one_or_none()

    if existing_draft is not None:
        return _build_draft_response(existing_draft, unready_gates)

    return PreviewShadowDraftResponse(
        source="shadow_project",
        status="idle",
        unready_gates=unready_gates,
    )


@router.get("/{draft_id}", response_model=PreviewShadowDraftResponse)
async def get_shadow_draft(
    project_id: str,
    draft_id: str,
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project)
):
    """
    Get detailed shadow draft status and payload.
    """
    ws_id = await _resolve_shadow_workspace(session, owned_project.id, branch, user.id)
    draft_res = await session.execute(
        select(PreviewShadowDraftModel).where(
            PreviewShadowDraftModel.project_id == owned_project.id,
            PreviewShadowDraftModel.workspace_id == ws_id,
            PreviewShadowDraftModel.draft_id == draft_id,
        )
    )
    draft = draft_res.scalar_one_or_none()
    if not draft:
        raise HTTPException(status_code=404, detail="shadow_draft_not_found")

    # Recalculate unready gates
    gates = await convergence_service.gate_evaluator.evaluate_gates(
        owned_project.id, session, workspace_id=ws_id
    )
    unready_gates = []
    if not gates["what"]:
        unready_gates.append("what")
    if not gates["how"]:
        unready_gates.append("how")
    if not gates["scope"]:
        unready_gates.append("scope")

    return _build_draft_response(draft, unready_gates)


@router.delete("/{draft_id}")
async def discard_shadow_draft(
    project_id: str,
    draft_id: str,
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project)
):
    """
    Soft discard shadow draft.
    """
    await _resolve_shadow_workspace(
        session, owned_project.id, branch, user.id, require_write=True
    )
    try:
        await convergence_service.discard_shadow_draft(owned_project.id, draft_id, session)
        return {"message": "shadow_draft_discarded"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{draft_id}/commit")
async def commit_shadow_draft(
    project_id: str,
    draft_id: str,
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project)
):
    """
    Commit shadow draft transaction-safe write-back.
    """
    await _resolve_shadow_workspace(
        session, owned_project.id, branch, user.id, require_write=True
    )
    try:
        await convergence_service.commit_shadow_draft(owned_project.id, draft_id, session)
        return {"message": "shadow_draft_committed"}
    except ValueError as e:
        if str(e) == "shadow_draft_conflict":
            raise HTTPException(
                status_code=409,
                detail="shadow_draft_conflict",
            )
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{draft_id}/regenerate", response_model=PreviewShadowDraftResponse)
async def regenerate_shadow_draft(
    project_id: str,
    draft_id: str,
    request: PreviewShadowRegenerateRequest,
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    llm_ctx: LLMRequestContext = Depends(get_llm_context),
    owned_project: ProjectModel = Depends(require_owned_project)
):
    """
    Force regenerate shadow convergence (e.g. following user adjustment request).
    """
    ws_id = await _resolve_shadow_workspace(
        session, owned_project.id, branch, user.id, require_write=True
    )
    draft_res = await session.execute(
        select(PreviewShadowDraftModel).where(
            PreviewShadowDraftModel.project_id == owned_project.id,
            PreviewShadowDraftModel.workspace_id == ws_id,
            PreviewShadowDraftModel.draft_id == draft_id,
        )
    )
    draft = draft_res.scalar_one_or_none()
    if not draft:
        raise HTTPException(status_code=404, detail="shadow_draft_not_found")

    # Regeneration binds the draft to the latest database snapshot.
    base_snapshot = await build_project_snapshot(owned_project.id, ws_id, session)
    current_hash = calculate_stable_snapshot_hash(base_snapshot)

    # Mark existing draft as regenerating with latest baseline snapshot
    draft.base_snapshot_json = base_snapshot
    draft.base_snapshot_hash = current_hash
    draft.status = "generating"
    draft.error_message = f"Regenerating draft with feedback: {request.user_feedback or ''}"
    await session.commit()

    # Respawn background convergence task
    _start_shadow_convergence(owned_project.id, draft_id, llm_ctx)

    # Recalculate unready gates
    gates = await convergence_service.gate_evaluator.evaluate_gates(
        owned_project.id, session, workspace_id=ws_id
    )
    unready_gates = []
    if not gates["what"]:
        unready_gates.append("what")
    if not gates["how"]:
        unready_gates.append("how")
    if not gates["scope"]:
        unready_gates.append("scope")

    return _build_draft_response(draft, unready_gates)
