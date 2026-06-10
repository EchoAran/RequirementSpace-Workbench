from __future__ import annotations
from backend.api.dependencies.ownership import require_owned_project

import asyncio
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.preview_shadow_schema import (
    PreviewShadowDraftResponse,
    PreviewShadowRegenerateRequest,
)
from backend.api.schemas.prototype_generation_schema import PrototypePreviewResponse
from backend.api.services.preview_shadow_convergence_service import (
    PreviewShadowConvergenceService,
    build_project_snapshot,
    calculate_stable_snapshot_hash,
)
from backend.api.services.service_registry import prototype_generation_service
from backend.database.database import get_session
from backend.database.model import PreviewShadowDraftModel, ProjectModel
from backend.api.dependencies.llm import get_llm_context
from backend.core.llm_context import LLMRequestContext

router = APIRouter(
    prefix="/api/projects/{project_id}/preview-shadow-drafts",
    tags=["preview-shadow"],
)

convergence_service = PreviewShadowConvergenceService()


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


@router.post("", response_model=PreviewShadowDraftResponse)
async def prepare_shadow_draft(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    llm_ctx: LLMRequestContext = Depends(get_llm_context),
    owned_project: ProjectModel = Depends(require_owned_project)
):
    """
    Prepare preview draft. If converged, loads or generates real prototype.
    If unconverged, retrieves or spawns shadow convergence.
    """
    # 1. Evaluate stage gates
    gates = await convergence_service.gate_evaluator.evaluate_gates(owned_project.id, session)
    all_passed = gates["what"] and gates["how"] and gates["scope"]

    if all_passed:
        # Converged: return real prototype
        try:
            preview = await prototype_generation_service.get_latest_preview(
                project_id=owned_project.id,
                session=session,
                raise_if_missing=False,
            )
            if preview is None:
                # Fallback: if no real preview exists, generate one automatically
                preview = await prototype_generation_service.generate_preview(
                    project_id=owned_project.id,
                    session=session,
                    force_regenerate=True,
                )
            return PreviewShadowDraftResponse(
                source="real_project",
                status="ready",
                prototype_preview=preview,
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to generate real preview: {str(e)}")

    # Unconverged: shadow mode
    unready_gates = []
    if not gates["what"]:
        unready_gates.append("what")
    if not gates["how"]:
        unready_gates.append("how")
    if not gates["scope"]:
        unready_gates.append("scope")

    # Build base snapshot
    base_snapshot = await build_project_snapshot(owned_project.id, session)
    current_hash = calculate_stable_snapshot_hash(base_snapshot)

    # 2. Check for duplicate active draft
    existing_res = await session.execute(
        select(PreviewShadowDraftModel)
        .where(
            PreviewShadowDraftModel.project_id == owned_project.id,
            PreviewShadowDraftModel.status.in_(["generating", "ready"]),
            PreviewShadowDraftModel.base_snapshot_hash == current_hash,
        )
        .order_by(PreviewShadowDraftModel.created_at.desc())
        .limit(1)
    )
    existing_draft = existing_res.scalar_one_or_none()
    
    if existing_draft is not None:
        return _build_draft_response(existing_draft, unready_gates)

    # 3. Mark all previous active drafts for this project as stale
    stale_drafts_res = await session.execute(
        select(PreviewShadowDraftModel).where(
            PreviewShadowDraftModel.project_id == owned_project.id,
            PreviewShadowDraftModel.status.in_(["generating", "ready"]),
        )
    )
    stale_drafts = stale_drafts_res.scalars().all()
    for sd in stale_drafts:
        sd.status = "stale"
        sd.error_message = "stale_by_new_snapshot"
    await session.flush()

    # 4. Create new shadow draft
    draft_id = f"draft_{uuid.uuid4().hex[:12]}"
    new_draft = PreviewShadowDraftModel(
        project_id=owned_project.id,
        draft_id=draft_id,
        status="generating",
        source="shadow_project",
        base_snapshot_hash=current_hash,
        base_snapshot_json=base_snapshot,
    )
    session.add(new_draft)
    await session.commit()  # Commit transaction so background task sees the record

    # 5. Spawn background convergence task
    asyncio.create_task(
        convergence_service.converge_shadow_snapshot_task(
            owned_project.id,
            draft_id,
            api_url=llm_ctx.api_url,
            api_key=llm_ctx.api_key,
            model_name=llm_ctx.model_name,
        )
    )

    return _build_draft_response(new_draft, unready_gates)


@router.get("/active", response_model=PreviewShadowDraftResponse)
async def get_active_shadow_draft(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project)
):
    """
    Get the current active shadow draft for the project if one exists.
    Returns status=idle if no active draft exists.
    """
    # 1. Evaluate stage gates
    gates = await convergence_service.gate_evaluator.evaluate_gates(owned_project.id, session)
    unready_gates = []
    if not gates["what"]:
        unready_gates.append("what")
    if not gates["how"]:
        unready_gates.append("how")
    if not gates["scope"]:
        unready_gates.append("scope")

    # Build base snapshot and hash to match active draft
    base_snapshot = await build_project_snapshot(owned_project.id, session)
    current_hash = calculate_stable_snapshot_hash(base_snapshot)

    # 2. Check for active draft matching current snapshot hash
    existing_res = await session.execute(
        select(PreviewShadowDraftModel)
        .where(
            PreviewShadowDraftModel.project_id == owned_project.id,
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
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project)
):
    """
    Get detailed shadow draft status and payload.
    """
    draft_res = await session.execute(
        select(PreviewShadowDraftModel).where(
            PreviewShadowDraftModel.project_id == owned_project.id,
            PreviewShadowDraftModel.draft_id == draft_id,
        )
    )
    draft = draft_res.scalar_one_or_none()
    if not draft:
        raise HTTPException(status_code=404, detail="shadow_draft_not_found")

    # Recalculate unready gates
    gates = await convergence_service.gate_evaluator.evaluate_gates(owned_project.id, session)
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
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project)
):
    """
    Soft discard shadow draft.
    """
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
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project)
):
    """
    Commit shadow draft transaction-safe write-back.
    """
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
    session: AsyncSession = Depends(get_session),
    llm_ctx: LLMRequestContext = Depends(get_llm_context),
    owned_project: ProjectModel = Depends(require_owned_project)
):
    """
    Force regenerate shadow convergence (e.g. following user adjustment request).
    """
    draft_res = await session.execute(
        select(PreviewShadowDraftModel).where(
            PreviewShadowDraftModel.project_id == owned_project.id,
            PreviewShadowDraftModel.draft_id == draft_id,
        )
    )
    draft = draft_res.scalar_one_or_none()
    if not draft:
        raise HTTPException(status_code=404, detail="shadow_draft_not_found")

    # 1. Re-build and update to the latest database snapshot and hash
    base_snapshot = await build_project_snapshot(owned_project.id, session)
    current_hash = calculate_stable_snapshot_hash(base_snapshot)

    # Mark existing draft as regenerating with latest baseline snapshot
    draft.base_snapshot_json = base_snapshot
    draft.base_snapshot_hash = current_hash
    draft.status = "generating"
    draft.error_message = f"Regenerating draft with feedback: {request.user_feedback or ''}"
    await session.commit()

    # Respawn background convergence task
    asyncio.create_task(
        convergence_service.converge_shadow_snapshot_task(
            owned_project.id,
            draft_id,
            api_url=llm_ctx.api_url,
            api_key=llm_ctx.api_key,
            model_name=llm_ctx.model_name,
        )
    )

    # Recalculate unready gates
    gates = await convergence_service.gate_evaluator.evaluate_gates(owned_project.id, session)
    unready_gates = []
    if not gates["what"]:
        unready_gates.append("what")
    if not gates["how"]:
        unready_gates.append("how")
    if not gates["scope"]:
        unready_gates.append("scope")

    return _build_draft_response(draft, unready_gates)
