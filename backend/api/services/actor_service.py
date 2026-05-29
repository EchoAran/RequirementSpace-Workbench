from sqlalchemy import select
from backend.database.model import ActorModel, AuditLogModel
from backend.api.services.perception_job_invalidation_service import (
    mark_perception_jobs_stale,
)
from backend.api.schemas.crud_schema import ActorCreateRequest, ActorUpdateRequest, ActorResponse


class ActorService:
    async def get_actors(self, project_id: int, session) -> list[ActorResponse]:
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

    async def create_actor(
        self,
        project_id: int,
        req: ActorCreateRequest,
        session,
    ) -> ActorResponse:
        actor = ActorModel(
            project_id=project_id,
            name=req.name,
            description=req.description,
        )
        session.add(actor)
        await session.flush()

        # 审计日志: 新增角色
        session.add(AuditLogModel(
            project_id=project_id,
            action_type="create_actor",
            summary=f"手动新增角色: {actor.name}",
            target_type="actor",
            target_id=str(actor.id),
            payload={},
        ))

        await mark_perception_jobs_stale(
            project_id=project_id,
            stages={"what"},
            perception_kinds={"ACTOR", "SCENARIO", "ACCEPTANCE_CRITERION"},
            session=session,
        )

        return ActorResponse(
            actor_id=actor.id,
            name=actor.name,
            description=actor.description,
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

        if req.name is not None:
            actor.name = req.name
        if req.description is not None:
            actor.description = req.description

        await session.flush()

        # 审计日志: 更新角色
        session.add(AuditLogModel(
            project_id=project_id,
            action_type="update_actor",
            summary=f"手动更新角色: {actor.name}",
            target_type="actor",
            target_id=str(actor.id),
            payload={},
        ))

        await mark_perception_jobs_stale(
            project_id=project_id,
            stages={"what"},
            perception_kinds={"ACTOR", "SCENARIO", "ACCEPTANCE_CRITERION"},
            session=session,
        )

        return ActorResponse(
            actor_id=actor.id,
            name=actor.name,
            description=actor.description,
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
        session.add(AuditLogModel(
            project_id=project_id,
            action_type="delete_actor",
            summary=f"手动删除角色: {actor_name}",
            target_type="actor",
            target_id=str(actor_id),
            payload={},
        ))

        await mark_perception_jobs_stale(
            project_id=project_id,
            stages={"what"},
            perception_kinds={"ACTOR", "SCENARIO", "ACCEPTANCE_CRITERION"},
            session=session,
        )

        return {
            "actor_id": actor_id,
            "message": "actor_deleted",
        }
