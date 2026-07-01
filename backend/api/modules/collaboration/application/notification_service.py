from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.model import NotificationModel
from backend.api.modules.collaboration.schemas.notifications import NotificationResponse

class NotificationService:
    async def list_notifications(self, user_id: int, session: AsyncSession) -> list[NotificationResponse]:
        stmt = select(NotificationModel).where(NotificationModel.recipient_user_id == user_id).order_by(NotificationModel.created_at.desc())
        res = await session.execute(stmt)
        notifications = res.scalars().all()
        return [
            NotificationResponse(
                id=n.id,
                recipient_user_id=n.recipient_user_id,
                project_id=n.project_id,
                task_id=n.task_id,
                event_type=n.event_type,
                title=n.title,
                body=n.body,
                read_at=n.read_at,
                created_at=n.created_at
            )
            for n in notifications
        ]

    async def mark_read(self, user_id: int, notification_ids: list[int] | None, session: AsyncSession) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        stmt = update(NotificationModel).where(NotificationModel.recipient_user_id == user_id).values(read_at=now)
        if notification_ids:
            stmt = stmt.where(NotificationModel.id.in_(notification_ids))
        else:
            stmt = stmt.where(NotificationModel.read_at == None)
        await session.execute(stmt)
        await session.flush()
