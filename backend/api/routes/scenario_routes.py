from backend.api.dependencies.ownership import require_owned_project
from backend.database.model import ProjectModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.crud_schema import (
    ScenarioCreateRequest,
    ScenarioUpdateRequest,
    ScenarioResponse,
    ACCreateRequest,
    ACUpdateRequest,
    ACResponse,
)
from backend.api.services.scenario_service import ScenarioService
from backend.database.database import get_session

router = APIRouter(
    prefix="/api/projects/{project_id}/scenarios",
    tags=["scenarios"],
)

scenario_service = ScenarioService()


@router.post("", response_model=ScenarioResponse)
async def create_scenario(
    project_id: str,
    request: ScenarioCreateRequest,
    session: AsyncSession = Depends(get_session),
 owned_project: ProjectModel = Depends(require_owned_project)):
    try:
        return await scenario_service.create_scenario(
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
            detail=f"Failed to create scenario: {error}",
        )


@router.put("/{scenario_id}", response_model=ScenarioResponse)
async def update_scenario(
    project_id: str,
    scenario_id: int,
    request: ScenarioUpdateRequest,
    session: AsyncSession = Depends(get_session),
 owned_project: ProjectModel = Depends(require_owned_project)):
    try:
        return await scenario_service.update_scenario(
            project_id=owned_project.id,
            scenario_id=scenario_id,
            req=request,
            session=session,
        )
    except ValueError as error:
        status = 404 if str(error) == "scenario_not_found" else 400
        raise HTTPException(
            status_code=status,
            detail=str(error),
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update scenario: {error}",
        )


@router.delete("/{scenario_id}")
async def delete_scenario(
    project_id: str,
    scenario_id: int,
    session: AsyncSession = Depends(get_session),
 owned_project: ProjectModel = Depends(require_owned_project)):
    try:
        return await scenario_service.delete_scenario(
            project_id=owned_project.id,
            scenario_id=scenario_id,
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
            detail=f"Failed to delete scenario: {error}",
        )


@router.post("/{scenario_id}/acceptance_criteria", response_model=ACResponse)
async def create_acceptance_criterion(
    project_id: str,
    scenario_id: int,
    request: ACCreateRequest,
    session: AsyncSession = Depends(get_session),
 owned_project: ProjectModel = Depends(require_owned_project)):
    try:
        return await scenario_service.create_ac(
            project_id=owned_project.id,
            scenario_id=scenario_id,
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
            detail=f"Failed to create acceptance criterion: {error}",
        )


@router.put("/{scenario_id}/acceptance_criteria/{ac_id}", response_model=ACResponse)
async def update_acceptance_criterion(
    project_id: str,
    scenario_id: int,
    ac_id: int,
    request: ACUpdateRequest,
    session: AsyncSession = Depends(get_session),
 owned_project: ProjectModel = Depends(require_owned_project)):
    try:
        return await scenario_service.update_ac(
            project_id=owned_project.id,
            scenario_id=scenario_id,
            ac_id=ac_id,
            req=request,
            session=session,
        )
    except ValueError as error:
        status = 404 if "not_found" in str(error) else 400
        raise HTTPException(
            status_code=status,
            detail=str(error),
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update acceptance criterion: {error}",
        )


@router.delete("/{scenario_id}/acceptance_criteria/{ac_id}")
async def delete_acceptance_criterion(
    project_id: str,
    scenario_id: int,
    ac_id: int,
    session: AsyncSession = Depends(get_session),
 owned_project: ProjectModel = Depends(require_owned_project)):
    try:
        return await scenario_service.delete_ac(
            project_id=owned_project.id,
            scenario_id=scenario_id,
            ac_id=ac_id,
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
            detail=f"Failed to delete acceptance criterion: {error}",
        )
