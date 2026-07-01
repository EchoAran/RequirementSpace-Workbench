from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import get_current_user
from backend.database.database import get_session
from backend.database.model import UserModel, ProjectModel
from backend.api.dependencies.ownership import require_owned_project
from backend.api.dependencies.project_access import require_project_role
from backend.api.modules.project_lifecycle.schemas.llm_config import (
    ProjectLLMConfigResponse,
    ProjectLLMConfigRequest,
    ProjectLLMConfigTestRequest,
    ProjectLLMConfigTestResponse,
)
from backend.api.modules.project_lifecycle.application.llm_config_service import ProjectLLMConfigService

router = APIRouter(
    prefix="/api/projects/{project_id}/llm-config",
    tags=["project_llm_config"],
)

llm_config_service = ProjectLLMConfigService()


@router.get("", response_model=ProjectLLMConfigResponse)
async def get_project_llm_config(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    project: ProjectModel = Depends(require_owned_project),
):
    try:
        return await llm_config_service.get_config(project.id, session)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve project LLM configuration: {str(exc)}",
        )


@router.put("", response_model=ProjectLLMConfigResponse)
async def update_project_llm_config(
    project_id: str,
    request: ProjectLLMConfigRequest,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    project: ProjectModel = Depends(require_project_role("admin")),
):
    try:
        return await llm_config_service.update_config(project.id, user.id, request, session)
    except ValueError as exc:
        error_msg = str(exc)
        if error_msg == "llm_config_invalid":
            raise HTTPException(status_code=400, detail=error_msg)
        raise HTTPException(status_code=400, detail="invalid_request")
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update project LLM configuration: {str(exc)}",
        )


@router.delete("")
async def delete_project_llm_config(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    project: ProjectModel = Depends(require_project_role("admin")),
):
    try:
        await llm_config_service.delete_config(project.id, session)
        return {"message": "llm_config_deleted"}
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete project LLM configuration: {str(exc)}",
        )


@router.post("/test", response_model=ProjectLLMConfigTestResponse)
async def test_project_llm_config(
    project_id: str,
    request: ProjectLLMConfigTestRequest,
    session: AsyncSession = Depends(get_session),
    project: ProjectModel = Depends(require_project_role("admin")),
):
    try:
        return await llm_config_service.test_config(project.id, request, session)
    except ValueError as exc:
        error_msg = str(exc)
        if error_msg in (
            "llm_config_required",
            "llm_config_invalid",
            "llm_config_test_failed",
        ):
            raise HTTPException(status_code=400, detail=error_msg)
        raise HTTPException(status_code=400, detail="invalid_request")
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Project LLM configuration test failed: {str(exc)}",
        )
