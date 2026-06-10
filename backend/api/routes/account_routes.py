from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import get_current_user
from backend.database.database import get_session
from backend.database.model import UserModel
from backend.api.schemas.account_schema import (
    LLMConfigResponse,
    LLMConfigRequest,
    LLMConfigTestRequest,
    LLMConfigTestResponse,
)
from backend.api.services.llm_config_service import LLMConfigService

router = APIRouter(
    prefix="/api/account/llm-config",
    tags=["account"],
)

llm_config_service = LLMConfigService()


@router.get("", response_model=LLMConfigResponse)
async def get_llm_config(
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await llm_config_service.get_config(user, session)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve LLM configuration: {str(exc)}",
        )


@router.put("", response_model=LLMConfigResponse)
async def update_llm_config(
    request: LLMConfigRequest,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await llm_config_service.update_config(user, request, session)
    except ValueError as exc:
        error_msg = str(exc)
        if error_msg in (
            "llm_config_invalid",
            "admin_cannot_configure_personal_llm",
        ):
            raise HTTPException(status_code=400, detail=error_msg)
        raise HTTPException(status_code=400, detail="invalid_request")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update LLM configuration: {str(exc)}",
        )


@router.delete("")
async def delete_llm_config(
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        await llm_config_service.delete_config(user, session)
        return {"message": "llm_config_deleted"}
    except ValueError as exc:
        error_msg = str(exc)
        if error_msg == "admin_cannot_configure_personal_llm":
            raise HTTPException(status_code=400, detail=error_msg)
        raise HTTPException(status_code=400, detail="invalid_request")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete LLM configuration: {str(exc)}",
        )


@router.post("/test", response_model=LLMConfigTestResponse)
async def test_llm_config(
    request: LLMConfigTestRequest,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await llm_config_service.test_config(user, request, session)
    except ValueError as exc:
        error_msg = str(exc)
        if error_msg in (
            "llm_config_required",
            "llm_config_invalid",
            "llm_config_test_failed",
            "server_llm_config_not_configured",
        ):
            raise HTTPException(status_code=400, detail=error_msg)
        raise HTTPException(status_code=400, detail="invalid_request")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"LLM configuration test failed: {str(exc)}",
        )
