from sqlalchemy import select, func, insert
from sqlalchemy.orm import selectinload
from backend.database.model import (
    FlowModel,
    FlowStepModel,
    FeatureModel,
    ActorModel,
    BusinessObjectModel,
    AuditLogModel,
    ConfirmationStatus,
    flow_feature_table,
    flow_step_actor_table,
    flow_step_input_business_object_table,
    flow_step_output_business_object_table,
    flow_step_next_table,
)
from backend.services.audit_service import AuditService

audit_service = AuditService()
from backend.api.modules.requirements_core.ports import get_notifier
from backend.api.modules.requirements_core.flow.schemas import (
    FlowCreateRequest,
    FlowUpdateRequest,
    FlowResponse,
    FlowStepCreateRequest,
    FlowStepUpdateRequest,
    FlowStepResponse,
    FlowStepsReorderRequest,
)


class FlowService:
    async def create_flow(
        self,
        project_id: int,
        req: FlowCreateRequest,
        session,
        confirmation_status: str = ConfirmationStatus.NEEDS_CONFIRMATION.value,
    ) -> FlowResponse:
        flow = FlowModel(
            project_id=project_id,
            name=req.name,
            description=req.description,
            confirmation_status=confirmation_status,
        )
        session.add(flow)
        await session.flush()

        if req.feature_ids:
            # 验证 feature 是否属于该项目
            features_result = await session.execute(
                select(FeatureModel.id).where(
                    FeatureModel.project_id == project_id,
                    FeatureModel.id.in_(req.feature_ids),
                )
            )
            valid_feature_ids = features_result.scalars().all()
            if len(valid_feature_ids) != len(req.feature_ids):
                raise ValueError("invalid_feature_ids")
            if valid_feature_ids:
                flow_feature_rows = [
                    {"flow_id": flow.id, "feature_id": feat_id}
                    for feat_id in valid_feature_ids
                ]
                await session.execute(
                    insert(flow_feature_table),
                    flow_feature_rows,
                )

        await session.flush()

        # 审计日志: 新增流程
        await audit_service.record(
            session=session,
            project_id=project_id,
            action_type="create_flow",
            summary=f"手动新增流程: {flow.name}",
            target_type="flow",
            target_id=flow.id,
            diff={"name": flow.name, "description": flow.description, "confirmation_status": flow.confirmation_status},
        )

        await get_notifier().mark_stale(
            project_id=project_id,
            stages={"how"},
            perception_kinds={"FLOW"},
            session=session,
        )

        return FlowResponse(
            flow_id=flow.id,
            name=flow.name,
            description=flow.description,
            feature_ids=req.feature_ids or [],
            steps=[],
            confirmation_status=flow.confirmation_status,
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
        
        from backend.api.modules.collaboration.application.task_service import snapshot_service
        await snapshot_service.check_optimistic_lock(session, "flow", flow, req.last_seen_updated_at)

        old_name = flow.name
        old_description = flow.description
        old_feature_ids = [feat.id for feat in flow.features]

        if req.name is not None:
            flow.name = req.name
        if req.description is not None:
            flow.description = req.description

        if req.feature_ids is not None:
            if req.feature_ids:
                features_result = await session.execute(
                    select(FeatureModel.id).where(
                        FeatureModel.project_id == project_id,
                        FeatureModel.id.in_(req.feature_ids),
                    )
                )
                valid_feature_ids = features_result.scalars().all()
                if len(valid_feature_ids) != len(req.feature_ids):
                    raise ValueError("invalid_feature_ids")
                
                features_models_result = await session.execute(
                    select(FeatureModel).where(
                        FeatureModel.id.in_(valid_feature_ids)
                    )
                )
                flow.features = features_models_result.scalars().all()
            else:
                flow.features = []

        await session.flush()

        # 审计日志: 更新流程
        diff = {}
        if old_name != flow.name:
            diff["name"] = {"before": old_name, "after": flow.name}
        if old_description != flow.description:
            diff["description"] = {"before": old_description, "after": flow.description}
        new_feature_ids = [feat.id for feat in flow.features]
        if old_feature_ids != new_feature_ids:
            diff["feature_ids"] = {"before": old_feature_ids, "after": new_feature_ids}

        await audit_service.record(
            session=session,
            project_id=project_id,
            action_type="update_flow",
            summary=f"手动更新流程: {flow.name}",
            target_type="flow",
            target_id=flow.id,
            diff=diff,
        )

        await get_notifier().mark_stale(
            project_id=project_id,
            stages={"how"},
            perception_kinds={"FLOW"},
            session=session,
        )

        from backend.api.modules.collaboration.application.task_service import snapshot_service
        await snapshot_service.supersede_tasks_on_node_update(session, "flow", flow)

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
        await audit_service.record(
            session=session,
            project_id=project_id,
            action_type="delete_flow",
            summary=f"手动删除流程: {flow_name}",
            target_type="flow",
            target_id=flow_id,
            diff={"status": "deleted"},
        )

        await get_notifier().mark_stale(
            project_id=project_id,
            stages={"how"},
            perception_kinds={"FLOW"},
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

        # 轻量约束校验
        if req.step_type == "actorAction" and not req.actor_ids:
            raise ValueError("actor_ids_cannot_be_empty_for_actor_action")

        pos_res = await session.execute(
            select(func.max(FlowStepModel.position)).where(
                FlowStepModel.flow_id == flow_id
            )
        )
        max_pos = pos_res.scalar()
        # Position starts at 1
        position = 1 if max_pos is None else max_pos + 1

        step = FlowStepModel(
            flow_id=flow_id,
            position=position,
            name=req.name,
            description=req.description,
            step_type=req.step_type,
            confirmation_status=ConfirmationStatus.NEEDS_CONFIRMATION.value,
        )
        session.add(step)
        await session.flush()

        # 审计日志: 新增流程步骤
        await audit_service.record(
            session=session,
            project_id=project_id,
            action_type="create_flow_step",
            summary=f"手动新增流程步骤: {step.name}",
            target_type="flow_step",
            target_id=step.id,
            diff={
                "name": step.name,
                "description": step.description,
                "step_type": step.step_type,
                "position": step.position,
                "confirmation_status": step.confirmation_status
            },
        )

        # Verify and insert relationships directly into association tables to avoid async lazy loading on newly created Step model
        if req.actor_ids:
            actors_res = await session.execute(
                select(ActorModel.id).where(
                    ActorModel.project_id == project_id,
                    ActorModel.id.in_(req.actor_ids),
                )
            )
            valid_actor_ids = actors_res.scalars().all()
            if len(valid_actor_ids) != len(req.actor_ids):
                raise ValueError("invalid_actor_ids")
            
            flow_step_actor_rows = [
                {"flow_step_id": step.id, "actor_id": act_id}
                for act_id in valid_actor_ids
            ]
            await session.execute(
                insert(flow_step_actor_table),
                flow_step_actor_rows,
            )

        if req.input_business_object_ids:
            bo_res = await session.execute(
                select(BusinessObjectModel.id).where(
                    BusinessObjectModel.project_id == project_id,
                    BusinessObjectModel.id.in_(req.input_business_object_ids),
                )
            )
            valid_input_bo_ids = bo_res.scalars().all()
            if len(valid_input_bo_ids) != len(req.input_business_object_ids):
                raise ValueError("invalid_input_business_object_ids")
            
            flow_step_input_bo_rows = [
                {"flow_step_id": step.id, "business_object_id": bo_id}
                for bo_id in valid_input_bo_ids
            ]
            await session.execute(
                insert(flow_step_input_business_object_table),
                flow_step_input_bo_rows,
            )

        if req.output_business_object_ids:
            bo_res = await session.execute(
                select(BusinessObjectModel.id).where(
                    BusinessObjectModel.project_id == project_id,
                    BusinessObjectModel.id.in_(req.output_business_object_ids),
                )
            )
            valid_output_bo_ids = bo_res.scalars().all()
            if len(valid_output_bo_ids) != len(req.output_business_object_ids):
                raise ValueError("invalid_output_business_object_ids")
            
            flow_step_output_bo_rows = [
                {"flow_step_id": step.id, "business_object_id": bo_id}
                for bo_id in valid_output_bo_ids
            ]
            await session.execute(
                insert(flow_step_output_business_object_table),
                flow_step_output_bo_rows,
            )

        if req.next_step_ids:
            next_res = await session.execute(
                select(FlowStepModel.id).where(
                    FlowStepModel.flow_id == flow_id,
                    FlowStepModel.id.in_(req.next_step_ids),
                )
            )
            valid_next_step_ids = next_res.scalars().all()
            if len(valid_next_step_ids) != len(req.next_step_ids):
                raise ValueError("invalid_next_step_ids")
            
            flow_step_next_rows = [
                {"source_step_id": step.id, "target_step_id": target_step_id}
                for target_step_id in valid_next_step_ids
            ]
            await session.execute(
                insert(flow_step_next_table),
                flow_step_next_rows,
            )

        await session.flush()

        # Reload the step with preloaded relationships for safe serialization
        reloaded_step_res = await session.execute(
            select(FlowStepModel)
            .where(FlowStepModel.id == step.id)
            .options(
                selectinload(FlowStepModel.actors),
                selectinload(FlowStepModel.input_business_objects),
                selectinload(FlowStepModel.output_business_objects),
                selectinload(FlowStepModel.next_steps),
            )
        )
        reloaded_step = reloaded_step_res.scalar_one()

        await get_notifier().mark_stale(
            project_id=project_id,
            stages={"how"},
            perception_kinds={"FLOW"},
            session=session,
        )

        return self._serialize_flow_step(reloaded_step)

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

        from backend.api.modules.collaboration.application.task_service import snapshot_service
        await snapshot_service.check_optimistic_lock(session, "flow_step", step, req.last_seen_updated_at)

        old_name = step.name
        old_description = step.description
        old_step_type = step.step_type
        old_actor_ids = [a.id for a in step.actors]
        old_input_bo_ids = [b.id for b in step.input_business_objects]
        old_output_bo_ids = [b.id for b in step.output_business_objects]
        old_next_step_ids = [s.id for s in step.next_steps]

        # 轻量约束校验
        new_step_type = req.step_type if req.step_type is not None else step.step_type
        new_actor_ids = req.actor_ids if req.actor_ids is not None else [actor.id for actor in step.actors]
        if new_step_type == "actorAction" and not new_actor_ids:
            raise ValueError("actor_ids_cannot_be_empty_for_actor_action")

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
                valid_actors = actors_res.scalars().all()
                if len(valid_actors) != len(req.actor_ids):
                    raise ValueError("invalid_actor_ids")
                step.actors = valid_actors
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
                valid_input_bos = bo_res.scalars().all()
                if len(valid_input_bos) != len(req.input_business_object_ids):
                    raise ValueError("invalid_input_business_object_ids")
                step.input_business_objects = valid_input_bos
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
                valid_output_bos = bo_res.scalars().all()
                if len(valid_output_bos) != len(req.output_business_object_ids):
                    raise ValueError("invalid_output_business_object_ids")
                step.output_business_objects = valid_output_bos
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
                valid_next_steps = next_res.scalars().all()
                if len(valid_next_steps) != len(req.next_step_ids):
                    raise ValueError("invalid_next_step_ids")
                step.next_steps = valid_next_steps
            else:
                step.next_steps = []

        await session.flush()

        # 审计日志: 更新流程步骤
        diff = {}
        if old_name != step.name:
            diff["name"] = {"before": old_name, "after": step.name}
        if old_description != step.description:
            diff["description"] = {"before": old_description, "after": step.description}
        if old_step_type != step.step_type:
            diff["step_type"] = {"before": old_step_type, "after": step.step_type}
        new_actor_ids = [a.id for a in step.actors]
        if old_actor_ids != new_actor_ids:
            diff["actor_ids"] = {"before": old_actor_ids, "after": new_actor_ids}
        new_input_bo_ids = [b.id for b in step.input_business_objects]
        if old_input_bo_ids != new_input_bo_ids:
            diff["input_business_object_ids"] = {"before": old_input_bo_ids, "after": new_input_bo_ids}
        new_output_bo_ids = [b.id for b in step.output_business_objects]
        if old_output_bo_ids != new_output_bo_ids:
            diff["output_business_object_ids"] = {"before": old_output_bo_ids, "after": new_output_bo_ids}
        new_next_step_ids = [s.id for s in step.next_steps]
        if old_next_step_ids != new_next_step_ids:
            diff["next_step_ids"] = {"before": old_next_step_ids, "after": new_next_step_ids}

        await audit_service.record(
            session=session,
            project_id=project_id,
            action_type="update_flow_step",
            summary=f"手动更新流程步骤: {step.name}",
            target_type="flow_step",
            target_id=step.id,
            diff=diff,
        )

        await get_notifier().mark_stale(
            project_id=project_id,
            stages={"how"},
            perception_kinds={"FLOW"},
            session=session,
        )

        from backend.api.modules.collaboration.application.task_service import snapshot_service
        await snapshot_service.supersede_tasks_on_node_update(session, "flow_step", step)

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

        # 查找被删除步骤的前驱和后继以进行拓扑修复
        pred_res = await session.execute(
            select(flow_step_next_table.c.source_step_id)
            .where(flow_step_next_table.c.target_step_id == step_id)
        )
        predecessors = pred_res.scalars().all()

        succ_res = await session.execute(
            select(flow_step_next_table.c.target_step_id)
            .where(flow_step_next_table.c.source_step_id == step_id)
        )
        successors = succ_res.scalars().all()

        step_name = step.name
        await session.delete(step)
        await session.flush()

        # 重新建立前驱和后继之间的直接关联来修复流程链
        for pred_id in predecessors:
            for succ_id in successors:
                exists = await session.execute(
                    select(1).select_from(flow_step_next_table)
                    .where(
                        flow_step_next_table.c.source_step_id == pred_id,
                        flow_step_next_table.c.target_step_id == succ_id
                    )
                    .limit(1)
                )
                if exists.scalar() is None:
                    await session.execute(
                        insert(flow_step_next_table).values(
                            source_step_id=pred_id,
                            target_step_id=succ_id
                        )
                    )

        # 审计日志: 删除流程步骤
        await audit_service.record(
            session=session,
            project_id=project_id,
            action_type="delete_flow_step",
            summary=f"手动删除流程步骤: {step_name}",
            target_type="flow_step",
            target_id=step_id,
            diff={"status": "deleted"},
        )

        # Re-index remaining flow step positions to prevent UniqueConstraint errors
        list_res = await session.execute(
            select(FlowStepModel)
            .where(FlowStepModel.flow_id == flow_id)
            .order_by(FlowStepModel.position.asc())
        )
        step_list = list_res.scalars().all()
        # Step 1: Negate positions to bypass constraints
        for idx, item in enumerate(step_list):
            item.position = -(idx + 1)
        await session.flush()

        # Step 2: Set final normalized 1..n positions
        for idx, item in enumerate(step_list):
            item.position = idx + 1
        await session.flush()

        await get_notifier().mark_stale(
            project_id=project_id,
            stages={"how"},
            perception_kinds={"FLOW"},
            session=session,
        )

        return {
            "step_id": step_id,
            "message": "flow_step_deleted",
        }

    async def reorder_flow_steps(
        self,
        project_id: int,
        flow_id: int,
        req: FlowStepsReorderRequest,
        session,
    ) -> FlowResponse:
        # 1. Verify flow belongs to project
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

        # 2. Strict validation of step_ids
        step_ids = req.step_ids
        if not step_ids:
            raise ValueError("step_ids_cannot_be_empty")
        
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("duplicate_step_ids")

        # Get all current steps in flow
        db_steps_res = await session.execute(
            select(FlowStepModel).where(FlowStepModel.flow_id == flow_id)
        )
        db_steps = {s.id: s for s in db_steps_res.scalars().all()}
        
        # Check set equality (no missing steps, no extra steps)
        if set(step_ids) != set(db_steps.keys()):
            raise ValueError("invalid_step_ids_match")

        # 3. Safe index negation to bypass SQLite UniqueConstraint
        for idx, sid in enumerate(step_ids):
            step = db_steps[sid]
            step.position = -(idx + 1)
        await session.flush()

        # Set final 1..n positions
        for idx, sid in enumerate(step_ids):
            step = db_steps[sid]
            step.position = idx + 1
        await session.flush()

        # 4. Sync linear topology connection (next_step_ids)
        # Clear existing next_step associations for all steps in this flow
        for sid in step_ids:
            await session.execute(
                flow_step_next_table.delete().where(
                    flow_step_next_table.c.source_step_id == sid
                )
            )
        await session.flush()

        # Link step i -> step i+1 consecutively, last step's next list is empty
        for i in range(len(step_ids) - 1):
            source_id = step_ids[i]
            target_id = step_ids[i+1]
            await session.execute(
                insert(flow_step_next_table).values(
                    source_step_id=source_id,
                    target_step_id=target_id
                )
            )
        await session.flush()

        # 5. Audit Log and Mark Perception Jobs Stale
        await audit_service.record(
            session=session,
            project_id=project_id,
            action_type="reorder_flow_steps",
            summary=f"手动重排流程步骤，流程: {flow.name}",
            target_type="flow",
            target_id=flow.id,
            diff={"step_ids": step_ids},
            payload={"step_ids": step_ids},
        )

        await get_notifier().mark_stale(
            project_id=project_id,
            stages={"how"},
            perception_kinds={"FLOW"},
            session=session,
        )

        session.expire_all()

        # Reload the flow to get clean relationships after the updates
        refreshed_result = await session.execute(
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
        refreshed_flow = refreshed_result.scalar_one()
        return self._serialize_flow(refreshed_flow)

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
            confirmation_status=step.confirmation_status,
        )

    def _serialize_flow(self, flow: FlowModel) -> FlowResponse:
        return FlowResponse(
            flow_id=flow.id,
            name=flow.name,
            description=flow.description,
            feature_ids=[f.id for f in flow.features],
            steps=[self._serialize_flow_step(st) for st in flow.steps],
            confirmation_status=flow.confirmation_status,
        )
