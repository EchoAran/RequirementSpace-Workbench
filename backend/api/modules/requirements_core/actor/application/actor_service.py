from sqlalchemy import select
from backend.database.model import ActorModel, AuditLogModel, ConfirmationStatus
from backend.api.modules.requirements_core.ports import get_notifier
from backend.api.modules.requirements_core.actor.schemas import ActorCreateRequest, ActorUpdateRequest, ActorResponse
from backend.services.audit_service import AuditService

audit_service = AuditService()


class ActorService:
    async def list_actors(self, project_id: int, session) -> list[ActorResponse]:
        result = await session.execute(
            select(ActorModel).where(ActorModel.project_id == project_id)
        )
        actors = result.scalars().all()
        return [
            ActorResponse(
                actor_id=actor.id,
                name=actor.name,
                description=actor.description,
            )
            for actor in actors
        ]

    async def get_actors(self, project_id: int, session) -> list[ActorResponse]:
        """Backward-compatible shim for list_actors."""
        return await self.list_actors(project_id, session)

    async def create_actor(
        self,
        project_id: int,
        req: ActorCreateRequest,
        session,
        confirmation_status: str = ConfirmationStatus.NEEDS_CONFIRMATION.value,
    ) -> ActorResponse:
        actor = ActorModel(
            project_id=project_id,
            name=req.name,
            description=req.description,
            confirmation_status=confirmation_status,
        )
        session.add(actor)
        await session.flush()

        # 审计日志: 新增角色
        diff = {"name": actor.name, "description": actor.description, "confirmation_status": confirmation_status}
        await audit_service.record(
            session=session,
            project_id=project_id,
            action_type="create_actor",
            summary=f"手动新增角色: {actor.name}",
            target_type="actor",
            target_id=actor.id,
            diff=diff,
        )

        await get_notifier().mark_stale(
            project_id=project_id,
            stages={"what"},
            perception_kinds={"ACTOR", "SCENARIO", "ACCEPTANCE_CRITERION"},
            session=session,
        )

        return ActorResponse(
            actor_id=actor.id,
            name=actor.name,
            description=actor.description,
            confirmation_status=actor.confirmation_status,
        )

    async def update_actor(
        self,
        project_id: int,
        actor_id: int,
        req: ActorUpdateRequest,
        session,
    ) -> ActorResponse:
        result = await session.execute(
            select(ActorModel).where(
                ActorModel.project_id == project_id,
                ActorModel.id == actor_id,
            )
        )
        actor = result.scalar_one_or_none()

        if actor is None:
            raise ValueError("actor_not_found")

        from backend.api.modules.collaboration.application.task_service import snapshot_service
        await snapshot_service.check_optimistic_lock(session, "actor", actor, req.last_seen_updated_at)

        old_name = actor.name
        old_description = actor.description

        if req.name is not None:
            actor.name = req.name
        if req.description is not None:
            actor.description = req.description

        await session.flush()

        # 审计日志: 更新角色
        diff = {}
        if old_name != actor.name:
            diff["name"] = {"before": old_name, "after": actor.name}
        if old_description != actor.description:
            diff["description"] = {"before": old_description, "after": actor.description}

        await audit_service.record(
            session=session,
            project_id=project_id,
            action_type="update_actor",
            summary=f"手动更新角色: {actor.name}",
            target_type="actor",
            target_id=actor.id,
            diff=diff,
        )

        await get_notifier().mark_stale(
            project_id=project_id,
            stages={"what"},
            perception_kinds={"ACTOR", "SCENARIO", "ACCEPTANCE_CRITERION"},
            session=session,
        )

        from backend.api.modules.collaboration.application.task_service import snapshot_service
        await snapshot_service.supersede_tasks_on_node_update(session, "actor", actor)

        return ActorResponse(
            actor_id=actor.id,
            name=actor.name,
            description=actor.description,
            confirmation_status=actor.confirmation_status,
        )

    async def delete_actor(
        self,
        project_id: int,
        actor_id: int,
        session,
    ) -> dict:
        result = await session.execute(
            select(ActorModel).where(
                ActorModel.project_id == project_id,
                ActorModel.id == actor_id,
            )
        )
        actor = result.scalar_one_or_none()

        if actor is None:
            raise ValueError("actor_not_found")

        actor_name = actor.name
        await session.delete(actor)
        await session.flush()

        # 审计日志: 删除角色
        await audit_service.record(
            session=session,
            project_id=project_id,
            action_type="delete_actor",
            summary=f"手动删除角色: {actor_name}",
            target_type="actor",
            target_id=actor_id,
            diff={"status": "deleted"},
        )

        await get_notifier().mark_stale(
            project_id=project_id,
            stages={"what"},
            perception_kinds={"ACTOR", "SCENARIO", "ACCEPTANCE_CRITERION"},
            session=session,
        )

        return {
            "actor_id": actor_id,
            "message": "actor_deleted",
        }
