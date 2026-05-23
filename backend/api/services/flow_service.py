from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from backend.database.model import (
    FlowModel,
    FlowStepModel,
    FeatureModel,
    ActorModel,
    BusinessObjectModel,
    AuditLogModel,
)
from backend.api.services.perception_job_invalidation_service import (
    mark_perception_jobs_stale,
)
from backend.api.schemas.crud_schema import (
    FlowCreateRequest,
    FlowUpdateRequest,
    FlowResponse,
    FlowStepCreateRequest,
    FlowStepUpdateRequest,
    FlowStepResponse,
)


class FlowService:
    async def create_flow(
        self,
        project_id: int,
        req: FlowCreateRequest,
        session,
    ) -> FlowResponse:
        flow = FlowModel(
            project_id=project_id,
            name=req.name,
            description=req.description,
        )
        session.add(flow)
        await session.flush()

        if req.feature_ids:
            features_result = await session.execute(
                select(FeatureModel).where(
                    FeatureModel.project_id == project_id,
                    FeatureModel.id.in_(req.feature_ids),
                )
            )
            flow.features = features_result.scalars().all()

        await session.flush()

        # 审计日志: 新增流程
        session.add(AuditLogModel(
            project_id=project_id,
            action_type="create_flow",
            summary=f"手动新增流程: {flow.name}",
            target_type="flow",
            target_id=str(flow.id),
            payload={},
        ))

        await mark_perception_jobs_stale(
            project_id=project_id,
            stages={"how"},
            session=session,
        )

        return FlowResponse(
            flow_id=flow.id,
            name=flow.name,
            description=flow.description,
            feature_ids=[f.id for f in flow.features],
            steps=[],
        )

    async def update_flow(
        self,
        project_id: int,
        flow_id: int,
        req: FlowUpdateRequest,
        session,
    ) -> FlowResponse:
        result = await session.execute(
            select(FlowModel)
            .where(
                FlowModel.project_id == project_id,
                FlowModel.id == flow_id,
            )
            .options(
                selectinload(FlowModel.features),
                selectinload(FlowModel.steps).selectinload(FlowStepModel.actors),
                selectinload(FlowModel.steps).selectinload(FlowStepModel.input_business_objects),
                selectinload(FlowModel.steps).selectinload(FlowStepModel.output_business_objects),
                selectinload(FlowModel.steps).selectinload(FlowStepModel.next_steps),
            )
        )
        flow = result.scalar_one_or_none()

        if flow is None:
            raise ValueError("flow_not_found")

        if req.name is not None:
            flow.name = req.name
        if req.description is not None:
            flow.description = req.description

        if req.feature_ids is not None:
            if req.feature_ids:
                features_result = await session.execute(
                    select(FeatureModel).where(
                        FeatureModel.project_id == project_id,
                        FeatureModel.id.in_(req.feature_ids),
                    )
                )
                flow.features = features_result.scalars().all()
            else:
                flow.features = []

        await session.flush()

        # 审计日志: 更新流程
        session.add(AuditLogModel(
            project_id=project_id,
            action_type="update_flow",
            summary=f"手动更新流程: {flow.name}",
            target_type="flow",
            target_id=str(flow.id),
            payload={},
        ))

        await mark_perception_jobs_stale(
            project_id=project_id,
            stages={"how"},
            session=session,
        )

        return self._serialize_flow(flow)

    async def delete_flow(
        self,
        project_id: int,
        flow_id: int,
        session,
    ) -> dict:
        result = await session.execute(
            select(FlowModel).where(
                FlowModel.project_id == project_id,
                FlowModel.id == flow_id,
            )
        )
        flow = result.scalar_one_or_none()

        if flow is None:
            raise ValueError("flow_not_found")

        flow_name = flow.name
        await session.delete(flow)
        await session.flush()

        # 审计日志: 删除流程
        session.add(AuditLogModel(
            project_id=project_id,
            action_type="delete_flow",
            summary=f"手动删除流程: {flow_name}",
            target_type="flow",
            target_id=str(flow_id),
            payload={},
        ))

        await mark_perception_jobs_stale(
            project_id=project_id,
            stages={"how"},
            session=session,
        )

        return {
            "flow_id": flow_id,
            "message": "flow_deleted",
        }

    async def create_flow_step(
        self,
        project_id: int,
        flow_id: int,
        req: FlowStepCreateRequest,
        session,
    ) -> FlowStepResponse:
        # Verify flow belongs to project
        flow_res = await session.execute(
            select(FlowModel).where(
                FlowModel.project_id == project_id,
                FlowModel.id == flow_id,
            )
        )
        if flow_res.scalar_one_or_none() is None:
            raise ValueError("flow_not_found")

        pos_res = await session.execute(
            select(func.count(FlowStepModel.id)).where(
                FlowStepModel.flow_id == flow_id
            )
        )
        position = pos_res.scalar() or 0

        step = FlowStepModel(
            flow_id=flow_id,
            position=position,
            name=req.name,
            description=req.description,
            step_type=req.step_type,
        )
        session.add(step)
        await session.flush()

        # Load and bind relationships
        if req.actor_ids:
            actors_res = await session.execute(
                select(ActorModel).where(
                    ActorModel.project_id == project_id,
                    ActorModel.id.in_(req.actor_ids),
                )
            )
            step.actors = actors_res.scalars().all()

        if req.input_business_object_ids:
            bo_res = await session.execute(
                select(BusinessObjectModel).where(
                    BusinessObjectModel.project_id == project_id,
                    BusinessObjectModel.id.in_(req.input_business_object_ids),
                )
            )
            step.input_business_objects = bo_res.scalars().all()

        if req.output_business_object_ids:
            bo_res = await session.execute(
                select(BusinessObjectModel).where(
                    BusinessObjectModel.project_id == project_id,
                    BusinessObjectModel.id.in_(req.output_business_object_ids),
                )
            )
            step.output_business_objects = bo_res.scalars().all()

        if req.next_step_ids:
            next_res = await session.execute(
                select(FlowStepModel).where(
                    FlowStepModel.flow_id == flow_id,
                    FlowStepModel.id.in_(req.next_step_ids),
                )
            )
            step.next_steps = next_res.scalars().all()

        await session.flush()

        await mark_perception_jobs_stale(
            project_id=project_id,
            stages={"how"},
            session=session,
        )

        return self._serialize_flow_step(step)

    async def update_flow_step(
        self,
        project_id: int,
        flow_id: int,
        step_id: int,
        req: FlowStepUpdateRequest,
        session,
    ) -> FlowStepResponse:
        # Verify flow belongs to project
        flow_res = await session.execute(
            select(FlowModel).where(
                FlowModel.project_id == project_id,
                FlowModel.id == flow_id,
            )
        )
        if flow_res.scalar_one_or_none() is None:
            raise ValueError("flow_not_found")

        step_res = await session.execute(
            select(FlowStepModel)
            .where(
                FlowStepModel.flow_id == flow_id,
                FlowStepModel.id == step_id,
            )
            .options(
                selectinload(FlowStepModel.actors),
                selectinload(FlowStepModel.input_business_objects),
                selectinload(FlowStepModel.output_business_objects),
                selectinload(FlowStepModel.next_steps),
            )
        )
        step = step_res.scalar_one_or_none()

        if step is None:
            raise ValueError("flow_step_not_found")

        if req.name is not None:
            step.name = req.name
        if req.description is not None:
            step.description = req.description
        if req.step_type is not None:
            step.step_type = req.step_type

        if req.actor_ids is not None:
            if req.actor_ids:
                actors_res = await session.execute(
                    select(ActorModel).where(
                        ActorModel.project_id == project_id,
                        ActorModel.id.in_(req.actor_ids),
                    )
                )
                step.actors = actors_res.scalars().all()
            else:
                step.actors = []

        if req.input_business_object_ids is not None:
            if req.input_business_object_ids:
                bo_res = await session.execute(
                    select(BusinessObjectModel).where(
                        BusinessObjectModel.project_id == project_id,
                        BusinessObjectModel.id.in_(req.input_business_object_ids),
                    )
                )
                step.input_business_objects = bo_res.scalars().all()
            else:
                step.input_business_objects = []

        if req.output_business_object_ids is not None:
            if req.output_business_object_ids:
                bo_res = await session.execute(
                    select(BusinessObjectModel).where(
                        BusinessObjectModel.project_id == project_id,
                        BusinessObjectModel.id.in_(req.output_business_object_ids),
                    )
                )
                step.output_business_objects = bo_res.scalars().all()
            else:
                step.output_business_objects = []

        if req.next_step_ids is not None:
            if req.next_step_ids:
                next_res = await session.execute(
                    select(FlowStepModel).where(
                        FlowStepModel.flow_id == flow_id,
                        FlowStepModel.id.in_(req.next_step_ids),
                    )
                )
                step.next_steps = next_res.scalars().all()
            else:
                step.next_steps = []

        await session.flush()

        await mark_perception_jobs_stale(
            project_id=project_id,
            stages={"how"},
            session=session,
        )

        return self._serialize_flow_step(step)

    async def delete_flow_step(
        self,
        project_id: int,
        flow_id: int,
        step_id: int,
        session,
    ) -> dict:
        # Verify flow belongs to project
        flow_res = await session.execute(
            select(FlowModel).where(
                FlowModel.project_id == project_id,
                FlowModel.id == flow_id,
            )
        )
        if flow_res.scalar_one_or_none() is None:
            raise ValueError("flow_not_found")

        step_res = await session.execute(
            select(FlowStepModel).where(
                FlowStepModel.flow_id == flow_id,
                FlowStepModel.id == step_id,
            )
        )
        step = step_res.scalar_one_or_none()

        if step is None:
            raise ValueError("flow_step_not_found")

        await session.delete(step)
        await session.flush()

        # Re-index remaining flow step positions to prevent UniqueConstraint errors
        list_res = await session.execute(
            select(FlowStepModel)
            .where(FlowStepModel.flow_id == flow_id)
            .order_by(FlowStepModel.position.asc())
        )
        step_list = list_res.scalars().all()
        for idx, item in enumerate(step_list):
            item.position = idx

        await session.flush()

        await mark_perception_jobs_stale(
            project_id=project_id,
            stages={"how"},
            session=session,
        )

        return {
            "step_id": step_id,
            "message": "flow_step_deleted",
        }

    @staticmethod
    def _serialize_flow_step(step: FlowStepModel) -> FlowStepResponse:
        return FlowStepResponse(
            step_id=step.id,
            flow_id=step.flow_id,
            position=step.position,
            name=step.name,
            description=step.description,
            step_type=step.step_type,
            actor_ids=[actor.id for actor in step.actors],
            input_business_object_ids=[bo.id for bo in step.input_business_objects],
            output_business_object_ids=[bo.id for bo in step.output_business_objects],
            next_step_ids=[ns.id for ns in step.next_steps],
        )

    def _serialize_flow(self, flow: FlowModel) -> FlowResponse:
        return FlowResponse(
            flow_id=flow.id,
            name=flow.name,
            description=flow.description,
            feature_ids=[f.id for f in flow.features],
            steps=[self._serialize_flow_step(st) for st in flow.steps],
        )
