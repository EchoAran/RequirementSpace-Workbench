from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any

from backend.api.dependencies.auth import get_current_user
from backend.database.database import get_session
from backend.database.model import UserModel, ProjectModel
from backend.api.dependencies.project_access import (
    require_project_member,
    require_project_role,
    require_project_config_read_access,
    require_project_config_write_access,
)
from backend.api.modules.project_configuration.schemas import (
    ProjectConfigurationResponse,
    ProjectConfigurationUpdate,
    GenerationStrategyConfigResponse,
    GenerationStrategyConfigUpdate,
    ProjectKnowledgeSummary,
    ProjectKnowledgeConfigUpdate,
)
from backend.api.modules.project_configuration.application.project_configuration_service import (
    ProjectConfigurationService,
)
from backend.api.modules.project_configuration.application.generation_strategy_config_service import (
    GenerationStrategyConfigService,
)
from backend.api.modules.project_configuration.application.content_locale_service import (
    ProjectContentLocaleService,
)

router = APIRouter(
    prefix="/api/projects/{project_id}/configuration",
    tags=["project_configuration"],
)

config_service = ProjectConfigurationService()
strategy_service = GenerationStrategyConfigService()
content_locale_service = ProjectContentLocaleService()


@router.get("", response_model=ProjectConfigurationResponse)
async def get_project_configuration(
    project_id: str,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    project: ProjectModel = Depends(require_project_config_read_access),
):
    """Retrieve aggregated project configurations summary."""
    try:
        return await config_service.get_configuration(
            project_id=project.id,
            project_public_id=project.public_id,
            content_locale=project.content_locale,
            user_id=user.id,
            session=session
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve project configuration: {str(exc)}",
        )


@router.put("", response_model=ProjectConfigurationResponse)
async def update_project_configuration(
    project_id: str,
    request: ProjectConfigurationUpdate,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    project: ProjectModel = Depends(require_project_config_write_access),
):
    """Update project configuration (requires owner/admin role)."""
    try:
        if "content_locale" in request.model_fields_set:
            changed = await content_locale_service.update(
                project=project,
                content_locale=request.content_locale,
                session=session,
            )
            if changed:
                await session.commit()

        return await config_service.get_configuration(
            project_id=project.id,
            project_public_id=project.public_id,
            content_locale=project.content_locale,
            user_id=user.id,
            session=session
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update project configuration: {str(exc)}",
        )



@router.get("/generation-strategies", response_model=GenerationStrategyConfigResponse)
async def get_generation_strategy_config(
    project_id: str,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Retrieve generation strategy configuration for the project."""
    project = await require_project_member(project_id, user, session)
    try:
        return await strategy_service.get_for_project(project.id, session)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve generation strategy configuration: {str(exc)}",
        )


@router.put("/generation-strategies", response_model=GenerationStrategyConfigResponse)
async def update_generation_strategy_config(
    project_id: str,
    request: GenerationStrategyConfigUpdate,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    project: ProjectModel = Depends(require_project_role("admin")),
):
    """Update generation strategy configuration (requires admin role)."""
    try:
        return await strategy_service.save_for_project(
            project_id=project.id,
            user_id=user.id,
            req=request,
            session=session
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update generation strategy configuration: {str(exc)}",
        )


@router.delete("/generation-strategies")
async def delete_generation_strategy_config(
    project_id: str,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    project: ProjectModel = Depends(require_project_role("admin")),
):
    """Reset generation strategy configuration back to default (requires admin role)."""
    try:
        await strategy_service.delete_for_project(project.id, session)
        return {"message": "generation_strategy_reset_to_default"}
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reset generation strategy configuration: {str(exc)}",
        )


@router.put("/knowledge", response_model=ProjectKnowledgeSummary)
async def update_project_knowledge_config(
    project_id: str,
    request: ProjectKnowledgeConfigUpdate,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    project: ProjectModel = Depends(require_project_role("admin")),
):
    """Update project-specific knowledge base toggle (requires admin role)."""
    try:
        return await config_service.save_knowledge_config(
            project_id=project.id,
            user_id=user.id,
            enabled=request.enabled,
            session=session
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update project knowledge configuration: {str(exc)}",
        )
