from sqlalchemy import delete, func, select

from backend.database.model import (
    ActorModel,
    BusinessObjectAttributeModel,
    BusinessObjectModel,
    FeatureModel,
    FeatureRelationModel,
    FlowModel,
    ScenarioModel,
    ScopeModel,
    feature_actor_table,
    flow_feature_table,
)


class GraphPatchEngine:
    async def apply_patch(self, project_id: int, patch: dict, session, workspace_id: int) -> None:
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

        await self._delete_nodes(
            project_id,
            patch.get("deleteNodes", []),
            session,
            workspace_id=workspace_id,
        )

        await self._add_nodes(
            project_id,
            patch.get("addNodes", []),
            temp_to_real_id,
            resolve_id,
            session,
            workspace_id=workspace_id,
        )

        await self._update_nodes(
            project_id,
            patch.get("updateNodes", []),
            resolve_id,
            session,
            workspace_id=workspace_id,
        )

        await self._add_links(
            patch.get("addLinks", []),
            resolve_id,
            session,
        )

    @staticmethod
    async def _update_nodes(project_id: int, nodes: list, resolve_id, session, workspace_id: int) -> None:
        for node in nodes:
            kind = node.get("kind")
            node_id_val = node.get("id") or node.get(f"{kind}Id") or node.get(f"{kind}_id")
            if not node_id_val:
                continue

            node_id = resolve_id(node_id_val, kind)

            if kind == "actor":
                res = await session.execute(select(ActorModel).where(ActorModel.id == node_id, ActorModel.project_id == project_id, ActorModel.workspace_id == workspace_id))
                actor = res.scalar_one_or_none()
                if actor:
                    if "name" in node or "actorName" in node:
                        actor.name = node.get("name") or node.get("actorName")
                    if "description" in node or "actorDescription" in node:
                        actor.description = node.get("description") or node.get("actorDescription")

            elif kind == "feature":
                res = await session.execute(select(FeatureModel).where(FeatureModel.id == node_id, FeatureModel.project_id == project_id, FeatureModel.workspace_id == workspace_id))
                feature = res.scalar_one_or_none()
                if feature:
                    if "name" in node or "featureName" in node:
                        feature.name = node.get("name") or node.get("featureName")
                    if "description" in node or "featureDescription" in node:
                        feature.description = node.get("description") or node.get("featureDescription")

            elif kind == "scenario":
                res = await session.execute(select(ScenarioModel).where(ScenarioModel.id == node_id, ScenarioModel.project_id == project_id, ScenarioModel.workspace_id == workspace_id))
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
                res = await session.execute(select(BusinessObjectModel).where(BusinessObjectModel.id == node_id, BusinessObjectModel.project_id == project_id, BusinessObjectModel.workspace_id == workspace_id))
                bo = res.scalar_one_or_none()
                if bo:
                    if "name" in node or "businessObjectName" in node or "boName" in node:
                        bo.name = node.get("name") or node.get("businessObjectName") or node.get("boName")
                    if "description" in node or "businessObjectDescription" in node or "boDescription" in node:
                        bo.description = node.get("description") or node.get("businessObjectDescription") or node.get("boDescription")

            elif kind == "flow":
                res = await session.execute(select(FlowModel).where(FlowModel.id == node_id, FlowModel.project_id == project_id, FlowModel.workspace_id == workspace_id))
                flow = res.scalar_one_or_none()
                if flow:
                    if "name" in node or "flowName" in node:
                        flow.name = node.get("name") or node.get("flowName")
                    if "description" in node or "flowDescription" in node:
                        flow.description = node.get("description") or node.get("flowDescription")

            elif kind == "scope":
                res = await session.execute(
                    select(ScopeModel).join(FeatureModel, ScopeModel.feature_id == FeatureModel.id)
                    .where(ScopeModel.id == node_id, FeatureModel.project_id == project_id, FeatureModel.workspace_id == workspace_id)
                )
                scope = res.scalar_one_or_none()
                if scope:
                    if "reason" in node:
                        scope.reason = node["reason"]
                    if "status" in node:
                        scope.status = node["status"]
                    elif "scopeStatus" in node or "scope_status" in node:
                        scope.status = node.get("scopeStatus") or node.get("scope_status")

    async def _add_nodes(
        self,
        project_id: int,
        nodes: list,
        temp_to_real_id: dict,
        resolve_id,
        session,
        workspace_id: int,
    ) -> None:
        for node in nodes:
            kind = node.get("kind")
            temp_id = node.get("temp_id") or node.get("tempId") or node.get("id")
            if kind == "actor":
                await self._add_actor(
                    project_id, node, temp_id, temp_to_real_id, session, workspace_id=workspace_id
                )
            elif kind == "feature":
                await self._add_feature(
                    project_id,
                    node,
                    temp_id,
                    temp_to_real_id,
                    resolve_id,
                    session,
                    workspace_id=workspace_id,
                )
            elif kind == "scenario":
                await self._add_scenario(
                    project_id,
                    node,
                    temp_id,
                    temp_to_real_id,
                    resolve_id,
                    session,
                    workspace_id=workspace_id,
                )
            elif kind == "business_object":
                await self._add_business_object(
                    project_id, node, temp_id, temp_to_real_id, session, workspace_id=workspace_id
                )
            elif kind == "flow":
                await self._add_flow(
                    project_id, node, temp_id, temp_to_real_id, session, workspace_id=workspace_id
                )
            elif kind == "business_object_attribute":
                await self._add_business_object_attribute(
                    node,
                    resolve_id,
                    session,
                )

    @staticmethod
    async def _add_actor(
        project_id: int,
        node: dict,
        temp_id,
        temp_to_real_id: dict,
        session,
        workspace_id: int,
    ) -> None:
        actor = ActorModel(
            project_id=project_id,
            workspace_id=workspace_id,
            name=node.get("name") or node.get("actorName") or "",
            description=node.get("description") or node.get("actorDescription") or "",
            confirmation_status="ai_assumption",
        )
        session.add(actor)
        await session.flush()
        if temp_id:
            temp_to_real_id[temp_id] = actor.id

    @staticmethod
    async def _add_feature(
        project_id: int,
        node: dict,
        temp_id,
        temp_to_real_id: dict,
        resolve_id,
        session,
        workspace_id: int,
    ) -> None:
        feature = FeatureModel(
            project_id=project_id,
            workspace_id=workspace_id,
            name=node.get("name") or node.get("featureName") or "",
            description=node.get("description") or node.get("featureDescription") or "",
            confirmation_status="ai_assumption",
        )
        session.add(feature)
        await session.flush()
        if temp_id:
            temp_to_real_id[temp_id] = feature.id

        parent_id_val = node.get("parent_id") or node.get("parentId")
        if parent_id_val is None:
            return
        parent_id = resolve_id(parent_id_val, "feature")
        position_result = await session.execute(
            select(func.max(FeatureRelationModel.position)).where(
                FeatureRelationModel.parent_feature_id == parent_id
            )
        )
        max_position = position_result.scalar()
        relation = FeatureRelationModel(
            parent_feature_id=parent_id,
            child_feature_id=feature.id,
            position=0 if max_position is None else max_position + 1,
        )
        session.add(relation)
        await session.flush()

    @staticmethod
    async def _add_scenario(
        project_id: int,
        node: dict,
        temp_id,
        temp_to_real_id: dict,
        resolve_id,
        session,
        workspace_id: int,
    ) -> None:
        feature_id_val = node.get("feature_id") or node.get("featureId")
        actor_id_val = node.get("actor_id") or node.get("actorId")
        if feature_id_val is None or actor_id_val is None:
            raise ValueError(
                "Scenario node insertion requires feature_id and actor_id"
            )
        scenario = ScenarioModel(
            project_id=project_id,
            workspace_id=workspace_id,
            feature_id=resolve_id(feature_id_val, "feature"),
            actor_id=resolve_id(actor_id_val, "actor"),
            name=node.get("name") or node.get("scenarioName") or "",
            content=node.get("content") or node.get("scenarioContent") or "",
            confirmation_status="ai_assumption",
        )
        session.add(scenario)
        await session.flush()
        if temp_id:
            temp_to_real_id[temp_id] = scenario.id

    @staticmethod
    async def _add_business_object(
        project_id: int,
        node: dict,
        temp_id,
        temp_to_real_id: dict,
        session,
        workspace_id: int,
    ) -> None:
        business_object = BusinessObjectModel(
            project_id=project_id,
            workspace_id=workspace_id,
            name=(
                node.get("name")
                or node.get("businessObjectName")
                or node.get("boName")
                or ""
            ),
            description=(
                node.get("description")
                or node.get("businessObjectDescription")
                or node.get("boDescription")
                or ""
            ),
            confirmation_status="ai_assumption",
        )
        session.add(business_object)
        await session.flush()
        if temp_id:
            temp_to_real_id[temp_id] = business_object.id

    @staticmethod
    async def _add_flow(
        project_id: int,
        node: dict,
        temp_id,
        temp_to_real_id: dict,
        session,
        workspace_id: int,
    ) -> None:
        flow = FlowModel(
            project_id=project_id,
            workspace_id=workspace_id,
            name=node.get("name") or node.get("flowName") or "",
            description=node.get("description") or node.get("flowDescription") or "",
            confirmation_status="ai_assumption",
        )
        session.add(flow)
        await session.flush()
        if temp_id:
            temp_to_real_id[temp_id] = flow.id

    @staticmethod
    async def _add_business_object_attribute(
        node: dict,
        resolve_id,
        session,
    ) -> None:
        business_object_id = resolve_id(
            node.get("business_object_id") or node.get("businessObjectId"),
            "business_object",
        )
        name = node.get("name", "")
        if not name:
            raise ValueError("business_object_attribute requires name")
        session.add(
            BusinessObjectAttributeModel(
                business_object_id=business_object_id,
                name=name,
                description=node.get("description", ""),
                data_type=node.get("data_type") or node.get("type") or "string",
                example=node.get("example", ""),
            )
        )

    async def _delete_nodes(self, project_id: int, nodes: list, session, workspace_id: int) -> None:
        for node in nodes:
            kind = node.get("kind")
            node_id_val = (
                node.get("id")
                or node.get(f"{kind}Id")
                or node.get(f"{kind}_id")
            )
            if not node_id_val:
                continue

            node_id = int(node_id_val)
            if kind == "actor":
                await session.execute(
                    delete(ActorModel).where(
                        ActorModel.id == node_id,
                        ActorModel.project_id == project_id,
                        ActorModel.workspace_id == workspace_id,
                    )
                )
            elif kind == "feature":
                feature = await session.scalar(select(FeatureModel).where(
                    FeatureModel.id == node_id,
                    FeatureModel.project_id == project_id,
                    FeatureModel.workspace_id == workspace_id,
                ))
                if feature is not None:
                    await self._delete_feature_recursive(feature.id, session)
            elif kind == "scenario":
                await session.execute(
                    delete(ScenarioModel).where(
                        ScenarioModel.id == node_id,
                        ScenarioModel.project_id == project_id,
                        ScenarioModel.workspace_id == workspace_id,
                    )
                )
            elif kind == "business_object":
                await session.execute(
                    delete(BusinessObjectModel).where(
                        BusinessObjectModel.id == node_id,
                        BusinessObjectModel.project_id == project_id,
                        BusinessObjectModel.workspace_id == workspace_id,
                    )
                )
            elif kind == "flow":
                await session.execute(
                    delete(FlowModel).where(
                        FlowModel.id == node_id,
                        FlowModel.project_id == project_id,
                        FlowModel.workspace_id == workspace_id,
                    )
                )

    @staticmethod
    async def _add_links(links: list, resolve_id, session) -> None:
        for link in links:
            source_id = (
                link.get("sourceId")
                or link.get("source_id")
                or link.get("source")
            )
            target_id = (
                link.get("targetId")
                or link.get("target_id")
                or link.get("target")
            )
            link_type = (
                link.get("type")
                or link.get("relationType")
                or link.get("relation_type")
            )
            if not source_id or not target_id:
                continue

            if link_type in ("feature_actor_relation", "feature_actor"):
                if "actor" in str(source_id) or "feature" in str(target_id):
                    feature_id = resolve_id(target_id, "feature")
                    actor_id = resolve_id(source_id, "actor")
                else:
                    feature_id = resolve_id(source_id, "feature")
                    actor_id = resolve_id(target_id, "actor")
                check = await session.execute(
                    select(feature_actor_table).where(
                        feature_actor_table.c.feature_id == feature_id,
                        feature_actor_table.c.actor_id == actor_id
                    )
                )
                if not check.first():
                    await session.execute(
                        feature_actor_table.insert().values(
                            feature_id=feature_id,
                            actor_id=actor_id,
                        )
                    )
            elif link_type in ("flow_feature_relation", "flow_feature"):
                if "feature" in str(source_id) or "flow" in str(target_id):
                    flow_id = resolve_id(target_id, "flow")
                    feature_id = resolve_id(source_id, "feature")
                else:
                    flow_id = resolve_id(source_id, "flow")
                    feature_id = resolve_id(target_id, "feature")
                check = await session.execute(
                    select(flow_feature_table).where(
                        flow_feature_table.c.flow_id == flow_id,
                        flow_feature_table.c.feature_id == feature_id
                    )
                )
                if not check.first():
                    await session.execute(
                        flow_feature_table.insert().values(
                            flow_id=flow_id,
                            feature_id=feature_id,
                        )
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
