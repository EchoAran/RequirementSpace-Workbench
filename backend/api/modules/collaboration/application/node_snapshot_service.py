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
from .node_snapshot_builders import build_node_snapshot
from .task_decision import supersede_tasks_for_node_update

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
        return await build_node_snapshot(session, node_kind, node)

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
        await supersede_tasks_for_node_update(
            session,
            node_kind,
            node,
            self.get_snapshot_and_hash,
        )
