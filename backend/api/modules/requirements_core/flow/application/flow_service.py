from sqlalchemy import insert, select

from backend.database.model import (
    ConfirmationStatus,
    FeatureModel,
    FlowModel,
    FlowStepModel,
    flow_feature_table,
)
from backend.services.audit_service import AuditService

from .flow_updater import (
    apply_flow_updates,
    build_flow_update_diff,
    capture_flow_state,
    load_flow_for_update,
)
from .steps import (
    apply_flow_step_relationship_updates,
    apply_flow_step_scalar_updates,
    apply_reordered_positions,
    build_flow_step_update_diff,
    capture_flow_step_state,
    cleanup_step_transition_rule_links,
    ensure_flow_exists,
    get_next_position_index,
    load_flow_for_reorder,
    load_flow_step,
    load_flow_step_for_update,
    load_flow_step_to_delete,
    normalize_flow_step_positions,
    validate_reordered_steps,
    write_flow_step_links,
)

audit_service = AuditService()
from backend.api.modules.requirements_core.flow.schemas import (
    FlowCreateRequest,
    FlowResponse,
    FlowStepCreateRequest,
    FlowStepResponse,
    FlowStepsReorderRequest,
    FlowStepUpdateRequest,
    FlowTransitionResponse,
    FlowUpdateRequest,
)
from backend.core.notifier import get_notifier


class FlowService:
    async def create_flow(
        self,
        project_id: int,
        req: FlowCreateRequest,
        session,
        confirmation_status: str = ConfirmationStatus.NEEDS_CONFIRMATION.value,
        *,
        workspace_id: int,
    ) -> FlowResponse:
        flow = FlowModel(
            project_id=project_id,
            workspace_id=workspace_id,
            name=req.name,
            description=req.description,
            confirmation_status=confirmation_status,
        )
        session.add(flow)
        await session.flush()

        if req.feature_ids:
            # 验证 feature 是否属于该项目和工作区
            stmt_feat = select(FeatureModel.id).where(
                FeatureModel.project_id == project_id,
                FeatureModel.id.in_(req.feature_ids),
            )
            stmt_feat = stmt_feat.where(FeatureModel.workspace_id == workspace_id)
            features_result = await session.execute(stmt_feat)
            valid_feature_ids = features_result.scalars().all()
            if len(valid_feature_ids) != len(req.feature_ids):
                raise ValueError("Cross-workspace entity reference rejected: invalid_feature_ids_or_workspace_mismatch")
            if valid_feature_ids:
                flow_feature_rows = [
                    {"flow_id": flow.id, "feature_id": feat_id}
                    for feat_id in valid_feature_ids
                ]
                await session.execute(insert(flow_feature_table).values(flow_feature_rows),)

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
            workspace_id=workspace_id,
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
        workspace_id: int,
    ) -> FlowResponse:
        stmt = select(FlowModel).where(
            FlowModel.project_id == project_id,
            FlowModel.id == flow_id,
        )
        stmt = stmt.where(FlowModel.workspace_id == workspace_id)
        exec_res = await session.execute(stmt)
        if exec_res.scalar_one_or_none() is None:
            raise ValueError("flow_not_found_in_workspace")

        flow = await load_flow_for_update(session, project_id, flow_id)

        from backend.api.modules.optimistic_lock.public import snapshot_service
        await snapshot_service.check_optimistic_lock(session, "flow", flow, req.last_seen_updated_at)

        before = capture_flow_state(flow)
        await apply_flow_updates(
            session,
            project_id=project_id,
            flow=flow,
            request=req,
        )

        await session.flush()

        # 审计日志: 更新流程
        diff = build_flow_update_diff(before, flow)

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
            workspace_id=workspace_id,
        )

        from backend.api.modules.optimistic_lock.public import snapshot_service
        await snapshot_service.supersede_tasks_on_node_update(session, "flow", flow)

        return self._serialize_flow(flow)

    async def delete_flow(
        self,
        project_id: int,
        flow_id: int,
        session,
        workspace_id: int,
    ) -> dict:
        stmt = select(FlowModel).where(
            FlowModel.project_id == project_id,
            FlowModel.id == flow_id,
        )
        stmt = stmt.where(FlowModel.workspace_id == workspace_id)
        result = await session.execute(stmt)
        flow = result.scalar_one_or_none()

        if flow is None:
            raise ValueError("flow_not_found_in_workspace")

        flow_name = flow.name
        await session.delete(flow)
        await session.flush()

        from backend.api.modules.requirements_core.domain_rule.domain.node_resolver import (
            RequirementNodeResolver,
        )
        await RequirementNodeResolver().sweep_orphaned_links(
            session=session,
            project_id=project_id,
            workspace_id=workspace_id,
        )

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
            workspace_id=workspace_id,
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
        workspace_id: int,
    ) -> FlowStepResponse:
        await ensure_flow_exists(session, project_id, flow_id, workspace_id=workspace_id)

        # 轻量约束校验
        if req.step_type == "actorAction" and not req.actor_ids:
            raise ValueError("actor_ids_cannot_be_empty_for_actor_action")

        position = await get_next_position_index(session, flow_id)

        step = FlowStepModel(
            workspace_id=workspace_id,
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

        await write_flow_step_links(
            session,
            project_id=project_id,
            flow_id=flow_id,
            step_id=step.id,
            actor_ids=req.actor_ids,
            input_business_object_ids=(
                req.input_business_object_ids
            ),
            output_business_object_ids=(
                req.output_business_object_ids
            ),
            workspace_id=workspace_id,
        )

        await session.flush()

        reloaded_step = await load_flow_step(session, step.id)

        await get_notifier().mark_stale(
            project_id=project_id,
            stages={"how"},
            perception_kinds={"FLOW"},
            session=session,
            workspace_id=workspace_id,
        )

        return self._serialize_flow_step(reloaded_step)

    async def update_flow_step(
        self,
        project_id: int,
        flow_id: int,
        step_id: int,
        req: FlowStepUpdateRequest,
        session,
        workspace_id: int,
    ) -> FlowStepResponse:
        await ensure_flow_exists(session, project_id, flow_id, workspace_id=workspace_id)
        step = await load_flow_step_for_update(session, flow_id, step_id, workspace_id=workspace_id)

        from backend.api.modules.optimistic_lock.public import snapshot_service
        await snapshot_service.check_optimistic_lock(session, "flow_step", step, req.last_seen_updated_at)

        before = capture_flow_step_state(step)

        # 轻量约束校验
        apply_flow_step_scalar_updates(step, req)
        await apply_flow_step_relationship_updates(
            session,
            project_id=project_id,
            flow_id=flow_id,
            step=step,
            request=req,
            workspace_id=workspace_id,
        )

        await session.flush()

        # 审计日志: 更新流程步骤
        diff = build_flow_step_update_diff(before, step)

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
            workspace_id=workspace_id,
        )

        from backend.api.modules.optimistic_lock.public import snapshot_service
        await snapshot_service.supersede_tasks_on_node_update(session, "flow_step", step)

        return self._serialize_flow_step(step)

    async def delete_flow_step(
        self,
        project_id: int,
        flow_id: int,
        step_id: int,
        session,
        workspace_id: int,
    ) -> dict:
        await ensure_flow_exists(session, project_id, flow_id, workspace_id=workspace_id)
        step = await load_flow_step_to_delete(session, flow_id, step_id, workspace_id=workspace_id)

        # Clean up rule links associated with transitions of the deleted step
        await cleanup_step_transition_rule_links(session, step_id)

        step_name = step.name
        await session.delete(step)
        await session.flush()

        from backend.api.modules.requirements_core.domain_rule.domain.node_resolver import (
            RequirementNodeResolver,
        )
        await RequirementNodeResolver().sweep_orphaned_links(
            session=session,
            project_id=project_id,
            workspace_id=workspace_id,
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
        await normalize_flow_step_positions(session, flow_id)

        await get_notifier().mark_stale(
            project_id=project_id,
            stages={"how"},
            perception_kinds={"FLOW"},
            session=session,
            workspace_id=workspace_id,
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
        workspace_id: int,
    ) -> FlowResponse:
        # Flow ownership defines the mutation boundary.
        await ensure_flow_exists(session, project_id, flow_id, workspace_id=workspace_id)
        flow = await load_flow_for_reorder(session, project_id, flow_id)

        # Every reordered step must belong to the selected flow.
        step_ids = req.step_ids
        db_steps = await validate_reordered_steps(
            session,
            flow_id,
            step_ids,
        )

        # Apply reordered positions without altering transitions/topology
        await apply_reordered_positions(session, step_ids, db_steps)

        # Topology changes invalidate dependent perception results.
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
            workspace_id=workspace_id,
        )

        session.expire_all()

        # Reload the flow to get clean relationships after the updates
        refreshed_flow = await load_flow_for_update(
            session,
            project_id,
            flow_id,
        )
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
            confirmation_status=step.confirmation_status,
        )

    def _serialize_flow(self, flow: FlowModel) -> FlowResponse:
        transitions = [
            FlowTransitionResponse(
                id=t.id,
                logical_uuid=t.logical_uuid,
                project_id=t.project_id,
                workspace_id=t.workspace_id,
                flow_id=t.flow_id,
                source_step_id=t.source_step_id,
                target_step_id=t.target_step_id,
                label=t.label,
                condition_text=t.condition_text,
                is_default=t.is_default,
                position=t.position,
                semantic_tags=t.semantic_tags or [],
                origin=t.origin,
                confirmation_status=t.confirmation_status,
                created_at=t.created_at,
                updated_at=t.updated_at,
            )
            for t in flow.transitions
        ]
        return FlowResponse(
            flow_id=flow.id,
            name=flow.name,
            description=flow.description,
            feature_ids=[f.id for f in flow.features],
            steps=[self._serialize_flow_step(st) for st in flow.steps],
            transitions=transitions,
            confirmation_status=flow.confirmation_status,
        )
