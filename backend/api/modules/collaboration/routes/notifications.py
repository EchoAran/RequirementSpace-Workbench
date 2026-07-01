from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import get_current_user
from backend.database.database import get_session
from backend.database.model import UserModel
from backend.api.modules.collaboration.schemas.notifications import (
    NotificationResponse,
    MarkNotificationsReadRequest,
)
from backend.api.modules.collaboration.application.notification_service import NotificationService

router = APIRouter(
    prefix="/api/me/notifications",
    tags=["notifications"],
)

notification_service = NotificationService()


@router.get("", response_model=list[NotificationResponse])
async def get_my_notifications(
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await notification_service.list_notifications(user.id, session)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve notifications: {str(exc)}",
        )


@router.put("/read")
async def mark_notifications_as_read(
    request: MarkNotificationsReadRequest,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        await notification_service.mark_read(user.id, request.notification_ids, session)
        return {"message": "notifications_marked_read"}
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to mark notifications as read: {str(exc)}",
        )
