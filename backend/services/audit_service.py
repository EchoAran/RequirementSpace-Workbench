import logging

from backend.database.model import AuditLogModel
from backend.core.actor_context import ActorContext, get_current_actor
from backend.core.logging import get_logger, log_event, sanitize_message
from backend.core.logging.events import (
    AUDIT_LOG_WRITE_COMPLETED,
    AUDIT_LOG_WRITE_FAILED,
)

logger = get_logger(__name__)


class AuditService:
    async def record(
        self,
        session,
        project_id: int,
        action_type: str,
        summary: str,
        target_type: str,
        target_id: str | int,
        actor: ActorContext | None = None,
        diff: dict | list | None = None,
        payload: dict | None = None,
        task_id: int | None = None,
    ) -> AuditLogModel:
        """Record a structured audit log event. Do not commit; caller controls transaction."""
        if actor is None:
            actor = get_current_actor()

        log_entry = AuditLogModel(
            project_id=project_id,
            action_type=action_type,
            summary=summary,
            target_type=target_type,
            target_id=str(target_id),
            actor_user_id=actor.user_id,
            actor_type=actor.actor_type,
            diff=diff,
            request_id=actor.request_id,
            task_id=task_id,
            payload=payload or {},
        )
        try:
            session.add(log_entry)
            await session.flush()
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "audit",
                AUDIT_LOG_WRITE_FAILED,
                "Audit log write failed",
                project_id=project_id,
                actor_user_id=actor.user_id,
                action_type=action_type,
                target_type=target_type,
                target_id=str(target_id),
                error_type=type(exc).__name__,
                error_message=sanitize_message(str(exc)),
            )
            raise

        log_event(
            logger,
            logging.INFO,
            "audit",
            AUDIT_LOG_WRITE_COMPLETED,
            "Audit log write completed",
            project_id=project_id,
            actor_user_id=actor.user_id,
            action_type=action_type,
            target_type=target_type,
            target_id=str(target_id),
        )
        return log_entry
