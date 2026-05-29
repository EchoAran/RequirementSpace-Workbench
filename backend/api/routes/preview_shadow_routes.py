from __future__ import annotations

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
from backend.api.services.prototype_generation_service import PrototypeGenerationService
from backend.database.database import get_session
from backend.database.model import PreviewShadowDraftModel, ProjectModel

router = APIRouter(
    prefix="/api/projects/{project_id}/preview-shadow-drafts",
    tags=["preview-shadow"],
)

convergence_service = PreviewShadowConvergenceService()
prototype_generation_service = PrototypeGenerationService()


@router.post("", response_model=PreviewShadowDraftResponse)
async def prepare_shadow_draft(
    project_id: int,
    session: AsyncSession = Depends(get_session),
):
    """
    Prepare preview draft. If converged, loads or generates real prototype.
    If unconverged, retrieves or spawns shadow convergence.
    """
    project = await session.get(ProjectModel, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="project_not_found")

    # 1. Evaluate stage gates
    gates = await convergence_service.gate_evaluator.evaluate_gates(project_id, session)
    all_passed = gates["what"] and gates["how"] and gates["scope"]

    if all_passed:
        # Converged: return real prototype
        try:
            preview = await prototype_generation_service.get_latest_preview(
                project_id=project_id,
                session=session,
                raise_if_missing=False,
            )
            if preview is None:
                # Fallback: if no real preview exists, generate one automatically
                preview = await prototype_generation_service.generate_preview(
                    project_id=project_id,
                    session=session,
                    force_regenerate=True,
                )
            return PreviewShadowDraftResponse(
                source="real_project",
                status="ready",
                prototype_preview=preview,
            )
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
    base_snapshot = await build_project_snapshot(project_id, session)
    current_hash = calculate_stable_snapshot_hash(base_snapshot)

    # 2. Check for duplicate active draft
    existing_res = await session.execute(
        select(PreviewShadowDraftModel)
        .where(
            PreviewShadowDraftModel.project_id == project_id,
            PreviewShadowDraftModel.status.in_(["generating", "ready"]),
            PreviewShadowDraftModel.base_snapshot_hash == current_hash,
        )
        .order_by(PreviewShadowDraftModel.created_at.desc())
        .limit(1)
    )
    existing_draft = existing_res.scalar_one_or_none()
    
    if existing_draft is not None:
        # Directly reuse
        preview_response = None
        if existing_draft.prototype_preview_json:
            # Map saved dictionary payload to PrototypePreviewResponse
            preview_response = PrototypePreviewResponse(**existing_draft.prototype_preview_json)
        
        # Calculate summary of shadow objects added
        patch = existing_draft.patch_json or {}
        shadow_summary = {
            "actors": len(patch.get("actors_added", [])),
            "features": len(patch.get("features_added", [])),
            "flows": len(patch.get("flows_added", [])),
            "scopes": len(patch.get("scopes_added", [])),
        }

        return PreviewShadowDraftResponse(
            source="shadow_project",
            draft_id=existing_draft.draft_id,
            status=existing_draft.status,
            unready_gates=unready_gates,
            shadow_summary=shadow_summary,
            prototype_preview=preview_response,
            shadow_snapshot_json=existing_draft.shadow_snapshot_json,
        )

    # 3. Mark all previous active drafts for this project as stale
    stale_drafts_res = await session.execute(
        select(PreviewShadowDraftModel).where(
            PreviewShadowDraftModel.project_id == project_id,
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
        project_id=project_id,
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
        convergence_service.converge_shadow_snapshot_task(project_id, draft_id)
    )

    return PreviewShadowDraftResponse(
        source="shadow_project",
        draft_id=draft_id,
        status="generating",
        unready_gates=unready_gates,
    )


@router.get("/{draft_id}", response_model=PreviewShadowDraftResponse)
async def get_shadow_draft(
    project_id: int,
    draft_id: str,
    session: AsyncSession = Depends(get_session),
):
    """
    Get detailed shadow draft status and payload.
    """
    draft_res = await session.execute(
        select(PreviewShadowDraftModel).where(
            PreviewShadowDraftModel.project_id == project_id,
            PreviewShadowDraftModel.draft_id == draft_id,
        )
    )
    draft = draft_res.scalar_one_or_none()
    if not draft:
        raise HTTPException(status_code=404, detail="shadow_draft_not_found")

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

    # Recalculate unready gates
    gates = await convergence_service.gate_evaluator.evaluate_gates(project_id, session)
    unready_gates = []
    if not gates["what"]:
        unready_gates.append("what")
    if not gates["how"]:
        unready_gates.append("how")
    if not gates["scope"]:
        unready_gates.append("scope")

    return PreviewShadowDraftResponse(
        source="shadow_project",
        draft_id=draft.draft_id,
        status=draft.status,
        unready_gates=unready_gates,
        shadow_summary=shadow_summary,
        prototype_preview=preview_response,
        shadow_snapshot_json=draft.shadow_snapshot_json,
    )


@router.delete("/{draft_id}")
async def discard_shadow_draft(
    project_id: int,
    draft_id: str,
    session: AsyncSession = Depends(get_session),
):
    """
    Soft discard shadow draft.
    """
    try:
        await convergence_service.discard_shadow_draft(project_id, draft_id, session)
        return {"message": "shadow_draft_discarded"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{draft_id}/commit")
async def commit_shadow_draft(
    project_id: int,
    draft_id: str,
    session: AsyncSession = Depends(get_session),
):
    """
    Commit shadow draft transaction-safe write-back.
    """
    try:
        await convergence_service.commit_shadow_draft(project_id, draft_id, session)
        return {"message": "shadow_draft_committed"}
    except ValueError as e:
        if str(e) == "shadow_draft_conflict":
            raise HTTPException(
                status_code=409,
                detail="shadow_draft_conflict",
            )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{draft_id}/regenerate", response_model=PreviewShadowDraftResponse)
async def regenerate_shadow_draft(
    project_id: int,
    draft_id: str,
    request: PreviewShadowRegenerateRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Force regenerate shadow convergence (e.g. following user adjustment request).
    """
    draft_res = await session.execute(
        select(PreviewShadowDraftModel).where(
            PreviewShadowDraftModel.project_id == project_id,
            PreviewShadowDraftModel.draft_id == draft_id,
        )
    )
    draft = draft_res.scalar_one_or_none()
    if not draft:
        raise HTTPException(status_code=404, detail="shadow_draft_not_found")

    # Mark existing draft as regenerating
    draft.status = "generating"
    draft.error_message = f"Regenerating draft with feedback: {request.user_feedback or ''}"
    await session.commit()

    # Respawn background convergence task
    asyncio.create_task(
        convergence_service.converge_shadow_snapshot_task(project_id, draft_id)
    )

    # Recalculate unready gates
    gates = await convergence_service.gate_evaluator.evaluate_gates(project_id, session)
    unready_gates = []
    if not gates["what"]:
        unready_gates.append("what")
    if not gates["how"]:
        unready_gates.append("how")
    if not gates["scope"]:
        unready_gates.append("scope")

    return PreviewShadowDraftResponse(
        source="shadow_project",
        draft_id=draft.draft_id,
        status="generating",
        unready_gates=unready_gates,
    )
