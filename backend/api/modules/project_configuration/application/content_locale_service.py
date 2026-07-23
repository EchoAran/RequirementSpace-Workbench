from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.locale import is_valid_locale
from backend.database.model import ProjectModel
from backend.services.audit_service import AuditService


class ProjectContentLocaleService:
    def __init__(self, audit_service: AuditService | None = None):
        self._audit_service = audit_service or AuditService()

    async def update(
        self,
        project: ProjectModel,
        content_locale: str | None,
        session: AsyncSession,
    ) -> bool:
        if content_locale is not None and not is_valid_locale(content_locale):
            raise ValueError("invalid_content_locale")
        old_locale = project.content_locale
        if old_locale == content_locale:
            return False

        project.content_locale = content_locale
        session.add(project)
        await session.flush()
        await self._audit_service.record(
            session=session,
            project_id=project.id,
            action_type="update_project_locale",
            summary=(
                "Updated project content language from "
                f"{old_locale or 'None'} to {content_locale or 'None'}"
            ),
            target_type="project",
            target_id=project.public_id,
            payload={"old_locale": old_locale, "new_locale": content_locale},
        )
        return True
