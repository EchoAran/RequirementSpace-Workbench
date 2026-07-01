from datetime import datetime
from pydantic import BaseModel, Field
from backend.api.base_schema import CamelModel

class NotificationResponse(CamelModel):
    id: int
    recipient_user_id: int
    project_id: int | None = None
    task_id: int | None = None
    event_type: str
    title: str
    body: str
    read_at: datetime | None = None
    created_at: datetime

class MarkNotificationsReadRequest(CamelModel):
    notification_ids: list[int] | None = Field(default=None, description="List of notification IDs to mark as read. If null or empty, marks all as read.")
