from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.ownership import require_owned_project, require_owned_generative_draft
from backend.api.dependencies.llm import get_llm_context, llm_context_manager
from backend.database.database import get_session
from backend.database.model import UserModel, ProjectModel, GenerativeDraftModel
from backend.api.modules.project_lifecycle.public import DraftRegenerateRequest
from backend.api.modules.requirements_core.feature.schemas import (
    FeatureCreateRequest,
    FeatureUpdateRequest,
    FeatureResponse,
    FeatureGenerationConfirmResponse,
    FeatureGenerationDraftCreateRequest,
    FeatureGenerationDraftDiscardResponse,
    FeatureGenerationDraftResponse,
)
from backend.api.modules.requirements_core.feature.application.feature_service import FeatureService
from backend.api.modules.requirements_core.feature.application.feature_generation_service import FeatureGenerationService


# 1. CRUD Router
crud_router = APIRouter(
    prefix="/api/projects/{project_id}/features",
    tags=["features"],
)

feature_service = FeatureService()


@crud_router.get("", response_model=list[FeatureResponse])
async def list_features(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project)
):
    try:
        return await feature_service.list_features(
            project_id=owned_project.id,
            session=session,
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch features: {error}",
        )


@crud_router.post("", response_model=FeatureResponse)
async def create_feature(
    project_id: str,
    request: FeatureCreateRequest,
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project)
):
    try:
        return await feature_service.create_feature(
            project_id=owned_project.id,
            req=request,
            session=session,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create feature: {error}",
        )


@crud_router.put("/{feature_id}", response_model=FeatureResponse)
async def update_feature(
    project_id: str,
    feature_id: int,
    request: FeatureUpdateRequest,
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project)
):
    try:
        return await feature_service.update_feature(
            project_id=owned_project.id,
            feature_id=feature_id,
            req=request,
            session=session,
        )
    except ValueError as error:
        status = 404 if str(error) == "feature_not_found" else 400
        raise HTTPException(
            status_code=status,
            detail=str(error),
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update feature: {error}",
        )


@crud_router.delete("/{feature_id}")
async def delete_feature(
    project_id: str,
    feature_id: int,
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project)
):
    try:
        return await feature_service.delete_feature(
            project_id=owned_project.id,
            feature_id=feature_id,
            session=session,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete feature: {error}",
        )


# 2. Generation Router
generation_router = APIRouter(
    prefix="/api/feature_generation_drafts",
    tags=["feature_generation"],
)

feature_generation_service = FeatureGenerationService()

FEATURE_GENERATION_ERRORS = {
    "project_not_found",
    "empty_features",
    "duplicate_feature_number",
    "invalid_feature_number_format",
    "missing_parent_feature",
    "invalid_root_feature_count",
    "invalid_actor_reference",
    "invalid_feature_payload",
    "invalid_skill_payload",
    "features_already_exist",
}


@generation_router.post(
    "",
    response_model=FeatureGenerationDraftResponse,
)
async def create_feature_generation_draft(
    request: FeatureGenerationDraftCreateRequest,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    owned_project = await require_owned_project(request.project_id, user, session)
    async with llm_context_manager(user, session, project_id=owned_project.id):
        try:
            return await feature_generation_service.create_draft(
                project_id=owned_project.id,
                owner_user_id=user.id,
                session=session,
            )
        except ValueError as error:
            if str(error) in FEATURE_GENERATION_ERRORS:
                raise HTTPException(
                    status_code=400,
                    detail=str(error),
                )
            raise


@generation_router.post(
    "/{draft_id}/regenerate",
    response_model=FeatureGenerationDraftResponse,
)
async def regenerate_feature_generation_draft(
    request: DraftRegenerateRequest | None = None,
    draft: GenerativeDraftModel = Depends(require_owned_generative_draft),
    session: AsyncSession = Depends(get_session),
    llm_ctx=Depends(get_llm_context),
):
    user_feedback = request.user_feedback if request else None
    try:
        return await feature_generation_service.regenerate_draft(
            draft_id=draft.draft_id,
            owner_user_id=draft.owner_user_id,
            session=session,
            user_feedback=user_feedback,
        )
    except ValueError as error:
        if str(error) == "draft_not_found":
            raise HTTPException(
                status_code=404,
                detail="draft_not_found",
            )
        if str(error) in FEATURE_GENERATION_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise


@generation_router.post(
    "/{draft_id}/confirm",
    response_model=FeatureGenerationConfirmResponse,
)
async def confirm_feature_generation_draft(
    draft: GenerativeDraftModel = Depends(require_owned_generative_draft),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await feature_generation_service.confirm_draft(
            draft_id=draft.draft_id,
            owner_user_id=draft.owner_user_id,
            session=session,
        )
    except ValueError as error:
        if str(error) == "draft_not_found":
            raise HTTPException(
                status_code=404,
                detail="draft_not_found",
            )
        if str(error) in FEATURE_GENERATION_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise


@generation_router.delete(
    "/{draft_id}",
    response_model=FeatureGenerationDraftDiscardResponse,
)
async def discard_feature_generation_draft(
    draft: GenerativeDraftModel = Depends(require_owned_generative_draft),
):
    return await feature_generation_service.discard_draft(
        draft_id=draft.draft_id,
        owner_user_id=draft.owner_user_id,
    )


router = crud_router
