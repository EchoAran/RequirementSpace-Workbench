from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager

from backend.api.dependencies.auth import get_current_user
from backend.database.model import UserModel
from backend.api.modules.auth_account.public import LLMConfigService
from backend.database.database import get_session
from backend.core.llm_context import current_llm_context, LLMRequestContext

llm_config_service = LLMConfigService()


@asynccontextmanager
async def llm_context_manager(user: UserModel, session: AsyncSession):
    """Context manager to resolve user LLM configuration and set request context."""
    try:
        config_data = await llm_config_service.resolve_for_user(user.id, session)
    except ValueError as e:
        err_msg = str(e)
        if err_msg in ("llm_config_required", "server_llm_config_not_configured"):
            raise HTTPException(status_code=409, detail=err_msg)
        raise HTTPException(status_code=400, detail=err_msg)

    api_url = config_data.get("api_url")
    api_key = config_data.get("api_key")
    model_name = config_data.get("model_name")

    if not api_url or not api_key or not model_name:
        raise HTTPException(status_code=409, detail="llm_config_required")

    ctx = LLMRequestContext(
        api_url=api_url,
        api_key=api_key,
        model_name=model_name
    )

    token = current_llm_context.set(ctx)
    try:
        yield ctx
    finally:
        current_llm_context.reset(token)


async def get_llm_context(
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> LLMRequestContext:
    """FastAPI dependency to resolve the current user's LLM configuration and set request context."""
    async with llm_context_manager(user, session) as ctx:
        yield ctx
