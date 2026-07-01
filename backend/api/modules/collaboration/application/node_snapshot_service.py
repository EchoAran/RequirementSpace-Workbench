import hashlib
import json
import sqlalchemy as sa
from sqlalchemy.orm import selectinload
from backend.database.model import (
    ActorModel,
    FeatureModel,
    ScenarioModel,
    ScenarioAcceptanceCriterionModel,
    BusinessObjectModel,
    BusinessObjectAttributeModel,
    FlowModel,
    FlowStepModel,
    ScopeModel,
)

KIND_TO_MODEL = {
    "actor": ActorModel,
    "feature": FeatureModel,
    "scenario": ScenarioModel,
    "acceptance_criterion": ScenarioAcceptanceCriterionModel,
    "business_object": BusinessObjectModel,
    "business_object_attribute": BusinessObjectAttributeModel,
    "flow": FlowModel,
    "flow_step": FlowStepModel,
    "scope": ScopeModel,
}

class NodeSnapshotService:
    async def get_snapshot_and_hash(self, session, node_kind: str, node_id: int) -> dict:
        """Load target node by kind and id, extract semantic fields, and compute a deterministic SHA-256 hash."""
        model_cls = KIND_TO_MODEL.get(node_kind.lower())
        if not model_cls:
            raise ValueError(f"Unsupported node kind: {node_kind}")

        # Set up selectinload options for eager loading relationships
        options = []
        if model_cls == FeatureModel:
            options.append(selectinload(FeatureModel.actors))
        elif model_cls == BusinessObjectModel:
            options.append(selectinload(BusinessObjectModel.attributes))
        elif model_cls == FlowModel:
            options.append(selectinload(FlowModel.steps))
        elif model_cls == FlowStepModel:
            options.append(selectinload(FlowStepModel.actors))
            options.append(selectinload(FlowStepModel.input_business_objects))
            options.append(selectinload(FlowStepModel.output_business_objects))

        query = sa.select(model_cls).where(model_cls.id == node_id).options(*options)
        res = await session.execute(query)
        node = res.scalar_one_or_none()
        if not node:
            raise ValueError(f"Node not found: {node_kind} with id {node_id}")

        snapshot = await self.build_snapshot(session, node_kind, node)
        
        # Serialize deterministically (sorted keys, no extra spacing)
        serialized = json.dumps(snapshot, sort_keys=True, separators=(',', ':'))
        content_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

        return {
            "snapshot": snapshot,
            "hash": content_hash,
            "node": node
        }

    async def build_snapshot(self, session, node_kind: str, node) -> dict:
        kind = node_kind.lower()
        from sqlalchemy import inspect
        ins = inspect(node)
        
        if kind == "actor":
            return {
                "name": node.name or "",
                "description": node.description or "",
            }
        elif kind == "feature":
            parent_id = None
            if "parent_relation" in ins.unloaded:
                from backend.database.model import FeatureRelationModel
                res_rel = await session.execute(
                    sa.select(FeatureRelationModel.parent_feature_id)
                    .where(FeatureRelationModel.child_feature_id == node.id)
                )
                parent_id = res_rel.scalar_one_or_none()
            else:
                parent_id = node.parent_relation.parent_feature_id if node.parent_relation else None

            actor_ids = []
            if "actors" in ins.unloaded:
                from backend.database.model import features_actors
                res_act = await session.execute(
                    sa.select(features_actors.c.actor_id)
                    .where(features_actors.c.feature_id == node.id)
                )
                actor_ids = [row[0] for row in res_act.all()]
            else:
                actor_ids = [a.id for a in node.actors] if node.actors else []

            return {
                "name": node.name or "",
                "description": node.description or "",
                "parent_id": parent_id,
                "actor_ids": sorted(actor_ids),
            }
        elif kind == "scenario":
            return {
                "name": node.name or "",
                "content": node.content or "",
                "feature_id": node.feature_id,
                "actor_id": node.actor_id,
            }
        elif kind == "acceptance_criterion":
            return {
                "content": node.content or "",
                "position": node.position,
                "scenario_id": node.scenario_id,
            }
        elif kind == "business_object":
            attributes = []
            if "attributes" in ins.unloaded:
                from backend.database.model import BusinessObjectAttributeModel
                res_attr = await session.execute(
                    sa.select(BusinessObjectAttributeModel)
                    .where(BusinessObjectAttributeModel.business_object_id == node.id)
                )
                attributes = res_attr.scalars().all()
            else:
                attributes = node.attributes or []

            attrs_data = []
            for attr in attributes:
                attrs_data.append({
                    "name": attr.name or "",
                    "description": attr.description or "",
                    "data_type": attr.data_type or "",
                    "example": attr.example or "",
                })
            attrs_data.sort(key=lambda x: x["name"])
            return {
                "name": node.name or "",
                "description": node.description or "",
                "attributes": attrs_data,
            }
        elif kind == "flow":
            steps = []
            if "steps" in ins.unloaded:
                from backend.database.model import FlowStepModel
                res_steps = await session.execute(
                    sa.select(FlowStepModel)
                    .where(FlowStepModel.flow_id == node.id)
                )
                steps = res_steps.scalars().all()
            else:
                steps = node.steps or []

            steps_data = []
            for step in steps:
                steps_data.append({
                    "position": step.position,
                    "name": step.name or "",
                    "description": step.description or "",
                    "step_type": step.step_type or "",
                })
            steps_data.sort(key=lambda x: x["position"])
            return {
                "name": node.name or "",
                "description": node.description or "",
                "steps": steps_data,
            }
        elif kind == "flow_step":
            actor_ids = []
            if "actors" in ins.unloaded:
                from backend.database.model import flow_steps_actors
                res_act = await session.execute(
                    sa.select(flow_steps_actors.c.actor_id)
                    .where(flow_steps_actors.c.flow_step_id == node.id)
                )
                actor_ids = [row[0] for row in res_act.all()]
            else:
                actor_ids = [a.id for a in node.actors] if node.actors else []

            input_business_object_ids = []
            if "input_business_objects" in ins.unloaded:
                from backend.database.model import flow_steps_input_business_objects
                res_ibo = await session.execute(
                    sa.select(flow_steps_input_business_objects.c.business_object_id)
                    .where(flow_steps_input_business_objects.c.flow_step_id == node.id)
                )
                input_business_object_ids = [row[0] for row in res_ibo.all()]
            else:
                input_business_object_ids = [b.id for b in node.input_business_objects] if node.input_business_objects else []

            output_business_object_ids = []
            if "output_business_objects" in ins.unloaded:
                from backend.database.model import flow_steps_output_business_objects
                res_obo = await session.execute(
                    sa.select(flow_steps_output_business_objects.c.business_object_id)
                    .where(flow_steps_output_business_objects.c.flow_step_id == node.id)
                )
                output_business_object_ids = [row[0] for row in res_obo.all()]
            else:
                output_business_object_ids = [b.id for b in node.output_business_objects] if node.output_business_objects else []

            return {
                "name": node.name or "",
                "description": node.description or "",
                "position": node.position,
                "step_type": node.step_type or "",
                "flow_id": node.flow_id,
                "actor_ids": sorted(actor_ids),
                "input_business_object_ids": sorted(input_business_object_ids),
                "output_business_object_ids": sorted(output_business_object_ids),
            }
        elif kind == "scope":
            return {
                "feature_id": node.feature_id,
                "status": node.status or "",
                "positive_summary": node.positive_summary or "",
                "negative_summary": node.negative_summary or "",
                "reason": node.reason or "",
                "kano_category": node.kano_category or "",
            }
        elif kind == "business_object_attribute":
            return {
                "name": node.name or "",
                "description": node.description or "",
                "data_type": node.data_type or "",
                "example": node.example or "",
            }
        else:
            raise ValueError(f"Unsupported node kind: {node_kind}")

    async def check_optimistic_lock(self, session, node_kind: str, node, last_seen_updated_at) -> None:
        if not last_seen_updated_at:
            return
        
        from datetime import datetime
        if isinstance(last_seen_updated_at, str):
            val = last_seen_updated_at.replace("Z", "")
            if "+" in val:
                val = val.split("+")[0]
            try:
                dt = datetime.fromisoformat(val)
            except ValueError:
                try:
                    dt = datetime.utcfromtimestamp(float(val))
                except ValueError:
                    return
        else:
            dt = last_seen_updated_at

        node_ts = node.updated_at.timestamp() if node.updated_at else 0
        dt_ts = dt.timestamp()
        
        if abs(node_ts - dt_ts) > 0.001:
            snap_res = await self.get_snapshot_and_hash(session, node_kind, node.id)
            from fastapi import HTTPException
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "node_content_changed",
                    "current_snapshot": snap_res["snapshot"]
                }
            )

    async def supersede_tasks_on_node_update(self, session, node_kind: str, node) -> None:
        from backend.database.model import CollaborationTaskModel, AuditLogModel
        
        stmt = sa.select(CollaborationTaskModel).where(
            sa.and_(
                CollaborationTaskModel.target_type == node_kind.lower(),
                CollaborationTaskModel.target_id == str(node.id),
                CollaborationTaskModel.status == "open"
            )
        )
        res = await session.execute(stmt)
        open_tasks = res.scalars().all()
        
        snap_res = await self.get_snapshot_and_hash(session, node_kind, node.id)
        current_hash = snap_res["hash"]
        
        for task in open_tasks:
            if task.content_hash != current_hash:
                task.status = "superseded"
                
                from backend.core.actor_context import get_current_actor
                act_ctx = get_current_actor()
                actor_user_id = act_ctx.user_id if act_ctx else None
                actor_type = act_ctx.actor_type if act_ctx else "system"
                actor_email = None
                request_id = act_ctx.request_id if act_ctx else None
                
                audit = AuditLogModel(
                    project_id=task.project_id,
                    action_type="task_superseded_by_node_update",
                    summary=f"Task {task.id} superseded by node update",
                    target_type="task",
                    target_id=str(task.id),
                    payload={
                        "task_id": task.id,
                        "node_kind": node_kind,
                        "node_id": node.id,
                        "old_hash": task.content_hash,
                        "new_hash": current_hash
                    },
                    actor_user_id=actor_user_id,
                    actor_type=actor_type,
                    request_id=request_id,
                    task_id=task.id
                )
                session.add(audit)
                
                from backend.database.model import NotificationModel
                notif = NotificationModel(
                    recipient_user_id=task.assigned_to_user_id,
                    project_id=task.project_id,
                    task_id=task.id,
                    event_type="task_superseded",
                    title="确认指派任务已失效",
                    body=f"您指派的确认任务 '{task.title}' 已失效，因为相关节点的内容已被更新。"
                )
                session.add(notif)
        
        batch_stmt = sa.select(CollaborationTaskModel).where(
            sa.and_(
                CollaborationTaskModel.task_type == "confirm_nodes",
                CollaborationTaskModel.status == "open"
            )
        )
        batch_res = await session.execute(batch_stmt)
        open_batch_tasks = batch_res.scalars().all()
        for task in open_batch_tasks:
            if task.targets:
                mismatch_found = False
                for pt in task.targets:
                    if pt.get("node_kind") == node_kind.lower() and str(pt.get("node_id")) == str(node.id):
                        if pt.get("hash") != current_hash:
                            mismatch_found = True
                
                if mismatch_found:
                    task.status = "superseded"
                    
                    from backend.core.actor_context import get_current_actor
                    act_ctx = get_current_actor()
                    actor_user_id = act_ctx.user_id if act_ctx else None
                    actor_type = act_ctx.actor_type if act_ctx else "system"
                    actor_email = None
                    request_id = act_ctx.request_id if act_ctx else None
                    
                    audit = AuditLogModel(
                        project_id=task.project_id,
                        action_type="task_superseded_by_node_update",
                        summary=f"Batch task {task.id} superseded by node update",
                        target_type="task",
                        target_id=str(task.id),
                        payload={
                            "task_id": task.id,
                            "node_kind": node_kind,
                            "node_id": node.id,
                            "batch": True
                        },
                        actor_user_id=actor_user_id,
                        actor_type=actor_type,
                        request_id=request_id,
                        task_id=task.id
                    )
                    session.add(audit)
                    
                    from backend.database.model import NotificationModel
                    notif = NotificationModel(
                        recipient_user_id=task.assigned_to_user_id,
                        project_id=task.project_id,
                        task_id=task.id,
                        event_type="task_superseded",
                        title="批量确认指派已失效",
                        body=f"您的批量确认任务 '{task.title}' 已失效，因为其中一个关联节点内容已被修改。"
                    )
                    session.add(notif)
