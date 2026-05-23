from sqlalchemy import select, func, delete
from sqlalchemy.orm import selectinload
from backend.database.model import (
    ActorModel,
    FeatureModel,
    FeatureRelationModel,
    ScenarioModel,
    BusinessObjectModel,
    FlowModel,
    feature_actor_table,
    flow_feature_table,
)

class GraphPatchEngine:
    async def apply_patch(self, project_id: int, patch: dict, session) -> None:
        """
        Applies a Graph Patch JSON dynamically to the SQLite database.
        The operations are executed inside the current transaction block.
        """
        temp_to_real_id = {}

        # Helper to resolve an ID (either integer physical ID or temp_id string mapping)
        def resolve_id(val: str | int, kind: str) -> int:
            val_str = str(val)
            if val_str.isdigit():
                return int(val_str)
            if val_str in temp_to_real_id:
                return temp_to_real_id[val_str]
            prefixed = f"{kind}:{val_str}"
            if prefixed in temp_to_real_id:
                return temp_to_real_id[prefixed]
            if ":" in val_str:
                parts = val_str.split(":", 1)
                part_val = parts[1]
                if part_val in temp_to_real_id:
                    return temp_to_real_id[part_val]
                prefixed_part = f"{kind}:{part_val}"
                if prefixed_part in temp_to_real_id:
                    return temp_to_real_id[prefixed_part]
                if part_val.isdigit():
                    return int(part_val)
            raise ValueError(f"Cannot resolve reference ID '{val}' for kind '{kind}'")

        # 1. Execute deletions (deleteNodes)
        for node in patch.get("deleteNodes", []):
            kind = node.get("kind")
            node_id_val = node.get("id") or node.get(f"{kind}Id") or node.get(f"{kind}_id")
            if not node_id_val:
                continue
            
            node_id = int(node_id_val)
            if kind == "actor":
                await session.execute(delete(ActorModel).where(ActorModel.id == node_id, ActorModel.project_id == project_id))
            elif kind == "feature":
                await self._delete_feature_recursive(node_id, session)
            elif kind == "scenario":
                await session.execute(delete(ScenarioModel).where(ScenarioModel.id == node_id, ScenarioModel.project_id == project_id))
            elif kind == "business_object":
                await session.execute(delete(BusinessObjectModel).where(BusinessObjectModel.id == node_id, BusinessObjectModel.project_id == project_id))
            elif kind == "flow":
                await session.execute(delete(FlowModel).where(FlowModel.id == node_id, FlowModel.project_id == project_id))

        # 2. Execute insertions (addNodes)
        for node in patch.get("addNodes", []):
            kind = node.get("kind")
            temp_id = node.get("temp_id") or node.get("tempId") or node.get("id")

            if kind == "actor":
                name = node.get("name") or node.get("actorName") or ""
                description = node.get("description") or node.get("actorDescription") or ""
                actor = ActorModel(
                    project_id=project_id,
                    name=name,
                    description=description,
                )
                session.add(actor)
                await session.flush()
                if temp_id:
                    temp_to_real_id[temp_id] = actor.id

            elif kind == "feature":
                name = node.get("name") or node.get("featureName") or ""
                description = node.get("description") or node.get("featureDescription") or ""
                feature = FeatureModel(
                    project_id=project_id,
                    name=name,
                    description=description,
                )
                session.add(feature)
                await session.flush()
                if temp_id:
                    temp_to_real_id[temp_id] = feature.id

                # Parent relation handling if provided
                parent_id_val = node.get("parent_id") or node.get("parentId")
                if parent_id_val is not None:
                    parent_id = resolve_id(parent_id_val, "feature")
                    # Check position
                    pos_result = await session.execute(
                        select(func.count(FeatureRelationModel.id)).where(
                            FeatureRelationModel.parent_feature_id == parent_id
                        )
                    )
                    position = pos_result.scalar() or 0

                    relation = FeatureRelationModel(
                        parent_feature_id=parent_id,
                        child_feature_id=feature.id,
                        position=position,
                    )
                    session.add(relation)
                    await session.flush()

            elif kind == "scenario":
                name = node.get("name") or node.get("scenarioName") or ""
                content = node.get("content") or node.get("scenarioContent") or ""
                
                feature_id_val = node.get("feature_id") or node.get("featureId")
                actor_id_val = node.get("actor_id") or node.get("actorId")
                
                if feature_id_val is None or actor_id_val is None:
                    raise ValueError("Scenario node insertion requires feature_id and actor_id")
                
                feature_id = resolve_id(feature_id_val, "feature")
                actor_id = resolve_id(actor_id_val, "actor")

                scenario = ScenarioModel(
                    project_id=project_id,
                    feature_id=feature_id,
                    actor_id=actor_id,
                    name=name,
                    content=content,
                )
                session.add(scenario)
                await session.flush()
                if temp_id:
                    temp_to_real_id[temp_id] = scenario.id

            elif kind == "business_object":
                name = node.get("name") or node.get("businessObjectName") or node.get("boName") or ""
                description = node.get("description") or node.get("businessObjectDescription") or node.get("boDescription") or ""
                bo = BusinessObjectModel(
                    project_id=project_id,
                    name=name,
                    description=description,
                )
                session.add(bo)
                await session.flush()
                if temp_id:
                    temp_to_real_id[temp_id] = bo.id

            elif kind == "flow":
                name = node.get("name") or node.get("flowName") or ""
                description = node.get("description") or node.get("flowDescription") or ""
                flow = FlowModel(
                    project_id=project_id,
                    name=name,
                    description=description,
                )
                session.add(flow)
                await session.flush()
                if temp_id:
                    temp_to_real_id[temp_id] = flow.id

        # 3. Execute updates (updateNodes)
        for node in patch.get("updateNodes", []):
            kind = node.get("kind")
            node_id_val = node.get("id") or node.get(f"{kind}Id") or node.get(f"{kind}_id")
            if not node_id_val:
                continue

            node_id = resolve_id(node_id_val, kind)

            if kind == "actor":
                res = await session.execute(select(ActorModel).where(ActorModel.id == node_id, ActorModel.project_id == project_id))
                actor = res.scalar_one_or_none()
                if actor:
                    if "name" in node or "actorName" in node:
                        actor.name = node.get("name") or node.get("actorName")
                    if "description" in node or "actorDescription" in node:
                        actor.description = node.get("description") or node.get("actorDescription")
            
            elif kind == "feature":
                res = await session.execute(select(FeatureModel).where(FeatureModel.id == node_id, FeatureModel.project_id == project_id))
                feature = res.scalar_one_or_none()
                if feature:
                    if "name" in node or "featureName" in node:
                        feature.name = node.get("name") or node.get("featureName")
                    if "description" in node or "featureDescription" in node:
                        feature.description = node.get("description") or node.get("featureDescription")
            
            elif kind == "scenario":
                res = await session.execute(select(ScenarioModel).where(ScenarioModel.id == node_id, ScenarioModel.project_id == project_id))
                scenario = res.scalar_one_or_none()
                if scenario:
                    if "name" in node or "scenarioName" in node:
                        scenario.name = node.get("name") or node.get("scenarioName")
                    if "content" in node or "scenarioContent" in node:
                        scenario.content = node.get("content") or node.get("scenarioContent")
                    if "featureId" in node or "feature_id" in node:
                        f_id = node.get("feature_id") or node.get("featureId")
                        scenario.feature_id = resolve_id(f_id, "feature")
                    if "actorId" in node or "actor_id" in node:
                        a_id = node.get("actor_id") or node.get("actorId")
                        scenario.actor_id = resolve_id(a_id, "actor")
            
            elif kind == "business_object":
                res = await session.execute(select(BusinessObjectModel).where(BusinessObjectModel.id == node_id, BusinessObjectModel.project_id == project_id))
                bo = res.scalar_one_or_none()
                if bo:
                    if "name" in node or "businessObjectName" in node or "boName" in node:
                        bo.name = node.get("name") or node.get("businessObjectName") or node.get("boName")
                    if "description" in node or "businessObjectDescription" in node or "boDescription" in node:
                        bo.description = node.get("description") or node.get("businessObjectDescription") or node.get("boDescription")
            
            elif kind == "flow":
                res = await session.execute(select(FlowModel).where(FlowModel.id == node_id, FlowModel.project_id == project_id))
                flow = res.scalar_one_or_none()
                if flow:
                    if "name" in node or "flowName" in node:
                        flow.name = node.get("name") or node.get("flowName")
                    if "description" in node or "flowDescription" in node:
                        flow.description = node.get("description") or node.get("flowDescription")

        # 4. Establish relation links (addLinks)
        for link in patch.get("addLinks", []):
            source_id = link.get("sourceId") or link.get("source_id") or link.get("source")
            target_id = link.get("targetId") or link.get("target_id") or link.get("target")
            link_type = link.get("type") or link.get("relationType") or link.get("relation_type")

            if not source_id or not target_id:
                continue

            if link_type == "feature_actor_relation" or link_type == "feature_actor":
                # Typically source is feature, target is actor (or vice versa)
                # Parse to check prefix or assume first is feature and second is actor
                if "actor" in str(source_id) or "feature" in str(target_id):
                    # Swapped
                    feature_id = resolve_id(target_id, "feature")
                    actor_id = resolve_id(source_id, "actor")
                else:
                    feature_id = resolve_id(source_id, "feature")
                    actor_id = resolve_id(target_id, "actor")

                # Verify relationship does not already exist
                check = await session.execute(
                    select(feature_actor_table).where(
                        feature_actor_table.c.feature_id == feature_id,
                        feature_actor_table.c.actor_id == actor_id
                    )
                )
                if not check.first():
                    await session.execute(
                        feature_actor_table.insert().values(feature_id=feature_id, actor_id=actor_id)
                    )

            elif link_type == "flow_feature_relation" or link_type == "flow_feature":
                if "feature" in str(source_id) or "flow" in str(target_id):
                    # Swapped
                    flow_id = resolve_id(target_id, "flow")
                    feature_id = resolve_id(source_id, "feature")
                else:
                    flow_id = resolve_id(source_id, "flow")
                    feature_id = resolve_id(target_id, "feature")

                # Verify relationship does not already exist
                check = await session.execute(
                    select(flow_feature_table).where(
                        flow_feature_table.c.flow_id == flow_id,
                        flow_feature_table.c.feature_id == feature_id
                    )
                )
                if not check.first():
                    await session.execute(
                        flow_feature_table.insert().values(flow_id=flow_id, feature_id=feature_id)
                    )

    async def _delete_feature_recursive(self, feature_id: int, session) -> None:
        """Helper to recursively delete feature and all its subfeatures."""
        child_relation_result = await session.execute(
            select(FeatureRelationModel.child_feature_id).where(
                FeatureRelationModel.parent_feature_id == feature_id
            )
        )
        child_ids = child_relation_result.scalars().all()

        for child_id in child_ids:
            await self._delete_feature_recursive(child_id, session)

        feature_result = await session.execute(
            select(FeatureModel).where(FeatureModel.id == feature_id)
        )
        feature = feature_result.scalar_one_or_none()
        if feature is not None:
            await session.delete(feature)
        await session.flush()
