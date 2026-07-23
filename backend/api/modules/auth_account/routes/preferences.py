from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import get_current_user
from backend.database.database import get_session
from backend.database.model import UserModel
from backend.api.modules.auth_account.schemas.preferences import (
    UpdatePreferencesRequest,
    PreferencesResponse,
)
from backend.api.modules.auth_account.application.preferences_service import (
    UserPreferencesService,
)

router = APIRouter(
    prefix="/api/account/preferences",
    tags=["account"],
)
preferences_service = UserPreferencesService()

@router.put("", response_model=PreferencesResponse)
async def update_preferences(
    request: UpdatePreferencesRequest,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        preferred_locale = await preferences_service.update_locale(
            user=user,
            preferred_locale=request.preferred_locale,
            session=session,
        )
        await session.commit()
        return PreferencesResponse(preferred_locale=preferred_locale)
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail="preference_update_failed",
        )
