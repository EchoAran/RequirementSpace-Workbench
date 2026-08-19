from sqlalchemy import select
from backend.database.model import ActorModel, ConfirmationStatus
from backend.core.notifier import get_notifier
from backend.api.modules.requirements_core.actor.schemas import ActorCreateRequest, ActorUpdateRequest, ActorResponse
from backend.services.audit_service import AuditService

audit_service = AuditService()


class ActorService:
    async def list_actors(self, project_id: int, session, workspace_id: int | None = None) -> list[ActorResponse]:
        stmt = select(ActorModel).where(ActorModel.project_id == project_id)
        if workspace_id is not None:
            stmt = stmt.where(ActorModel.workspace_id == workspace_id)
        exec_res = session.execute(stmt)
        if hasattr(exec_res, "__await__"):
            result = await exec_res
        else:
            result = exec_res
        actors = result.scalars().all()
        return [
            ActorResponse(
                actor_id=actor.id,
                name=actor.name,
                description=actor.description,
            )
            for actor in actors
        ]

    async def get_actors(self, project_id: int, session, workspace_id: int | None = None) -> list[ActorResponse]:
        """Backward-compatible shim for list_actors."""
        return await self.list_actors(project_id, session, workspace_id)

    async def create_actor(
        self,
        project_id: int,
        req: ActorCreateRequest,
        session,
        confirmation_status: str = ConfirmationStatus.NEEDS_CONFIRMATION.value,
        workspace_id: int | None = None,
    ) -> ActorResponse:
        actor = ActorModel(
            project_id=project_id,
            workspace_id=workspace_id,
            name=req.name,
            description=req.description,
            confirmation_status=confirmation_status,
        )
        session.add(actor)
        flush_res = session.flush()
        if hasattr(flush_res, "__await__"):
            await flush_res

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
        workspace_id: int | None = None,
    ) -> ActorResponse:
        stmt = select(ActorModel).where(
            ActorModel.project_id == project_id,
            ActorModel.id == actor_id,
        )
        if workspace_id is not None:
            stmt = stmt.where(ActorModel.workspace_id == workspace_id)
        exec_res = session.execute(stmt)
        if hasattr(exec_res, "__await__"):
            result = await exec_res
        else:
            result = exec_res
        actor = result.scalar_one_or_none()

        if actor is None:
            raise ValueError("actor_not_found_in_workspace")

        from backend.api.modules.optimistic_lock.public import snapshot_service
        await snapshot_service.check_optimistic_lock(session, "actor", actor, req.last_seen_updated_at)

        old_name = actor.name
        old_description = actor.description

        if req.name is not None:
            actor.name = req.name
        if req.description is not None:
            actor.description = req.description

        flush_res = session.flush()
        if hasattr(flush_res, "__await__"):
            await flush_res

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

        from backend.api.modules.optimistic_lock.public import snapshot_service
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
        workspace_id: int | None = None,
    ) -> dict:
        stmt = select(ActorModel).where(
            ActorModel.project_id == project_id,
            ActorModel.id == actor_id,
        )
        if workspace_id is not None:
            stmt = stmt.where(ActorModel.workspace_id == workspace_id)
        exec_res = session.execute(stmt)
        if hasattr(exec_res, "__await__"):
            result = await exec_res
        else:
            result = exec_res
        actor = result.scalar_one_or_none()

        if actor is None:
            raise ValueError("actor_not_found_in_workspace")

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
