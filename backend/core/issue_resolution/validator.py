"""Patch Validator for Issue Repair drafts.

Three-layer validation:
1. Structural: operation name whitelist, required fields
2. Reference: target entity existence in project
3. Domain: issue-specific business rules
"""

from sqlalchemy import select
from backend.database.model import (
    ActorModel,
    BusinessObjectAttributeModel,
    BusinessObjectModel,
    FeatureModel,
    FlowModel,
    ScenarioModel,
    ScopeModel,
    feature_actor_table,
)

# P4 whitelist: only these operations are allowed
ALLOWED_OPERATIONS = {"updateNodes", "addLinks", "addNodes"}

# Allowed operation + kind combinations with required fields
ALLOWED_PATCH_PATTERNS: dict[str, set[str]] = {
    "updateNodes": {"scope", "scenario"},
    "addLinks": {"feature_actor_relation", "feature_actor", "flow_feature_relation", "flow_feature"},
    "addNodes": {"business_object_attribute"},
}

# Valid data types for business object attributes
VALID_ATTRIBUTE_TYPES = {"string", "integer", "float", "boolean", "date", "datetime", "text"}


class PatchValidationError(ValueError):
    """Raised when a patch fails validation."""
    pass


class RepairValidator:
    """Validates repair draft patches before they are stored or applied."""

    # ---- Layer 1: Structural validation ----

    def validate_structure(self, patch: dict) -> None:
        """Check operation names and required fields."""
        if not isinstance(patch, dict):
            raise PatchValidationError("patch 必须是一个 JSON 对象")

        for op in patch:
            if op not in ALLOWED_OPERATIONS:
                raise PatchValidationError(f"不允许的操作: {op}")

        # Validate updateNodes
        for node in patch.get("updateNodes", []):
            kind = node.get("kind")
            if not kind:
                raise PatchValidationError("updateNodes 条目缺少 kind 字段")
            allowed = ALLOWED_PATCH_PATTERNS.get("updateNodes", set())
            if kind not in allowed:
                raise PatchValidationError(f"updateNodes 不允许的 kind: {kind}")

            node_id = node.get("id")
            if not node_id:
                raise PatchValidationError(f"updateNodes ({kind}) 缺少 id")

            # kind-specific required fields
            if kind == "scope" and "reason" not in node:
                raise PatchValidationError("scope updateNodes 必须包含 reason 字段")

        # Validate addLinks
        for link in patch.get("addLinks", []):
            link_type = link.get("type") or link.get("relationType") or link.get("relation_type")
            if not link_type:
                raise PatchValidationError("addLinks 条目缺少 type 字段")

            allowed = ALLOWED_PATCH_PATTERNS.get("addLinks", set())
            if link_type not in allowed:
                raise PatchValidationError(f"addLinks 不允许的类型: {link_type}")

            source_id = link.get("sourceId") or link.get("source_id") or link.get("source")
            target_id = link.get("targetId") or link.get("target_id") or link.get("target")
            if not source_id or not target_id:
                raise PatchValidationError(f"addLinks ({link_type}) 缺少 source 或 target")

    # ---- Layer 2: Reference validation ----

    async def validate_references(self, project_id: int, patch: dict, session) -> None:
        """Check that all referenced entities exist in the project."""
        for node in patch.get("updateNodes", []):
            kind = node.get("kind")
            node_id = int(node.get("id"))
            exists = await self._entity_exists(project_id, kind, node_id, session)
            if not exists:
                raise PatchValidationError(f"{kind} (id={node_id}) 在当前项目中不存在")

        for link in patch.get("addLinks", []):
            link_type = link.get("type") or link.get("relationType") or link.get("relation_type")
            source_id = int(link.get("sourceId") or link.get("source_id") or link.get("source"))
            target_id = int(link.get("targetId") or link.get("target_id") or link.get("target"))

            if link_type in ("feature_actor_relation", "feature_actor"):
                # source is typically feature, target is actor
                if not await self._entity_exists(project_id, "feature", source_id, session):
                    raise PatchValidationError(f"feature (id={source_id}) 不存在")
                if not await self._entity_exists(project_id, "actor", target_id, session):
                    raise PatchValidationError(f"actor (id={target_id}) 不存在")

    # ---- Layer 3: Domain-specific validation ----

    async def validate_domain(
        self,
        project_id: int,
        issue_code: str,
        patch: dict,
        session,
    ) -> None:
        """Issue-family-specific business rules."""
        if "updateNodes" in patch:
            for node in patch.get("updateNodes", []):
                kind = node.get("kind")
                if kind == "scope":
                    reason = node.get("reason", "")
                    if not reason or not reason.strip():
                        raise PatchValidationError("scope reason 不能为空")
                    if len(reason) > 2000:
                        raise PatchValidationError("scope reason 过长 (最大 2000 字符)")
                elif kind == "scenario":
                    if "feature_id" in node or "featureId" in node:
                        f_id = int(node.get("feature_id") or node.get("featureId"))
                        if not await self._entity_exists(project_id, "feature", f_id, session):
                            raise PatchValidationError(f"scenario.feature_id (id={f_id}) 不存在")

        if "addLinks" in patch:
            for link in patch.get("addLinks", []):
                link_type = link.get("type") or link.get("relationType") or link.get("relation_type")
                source_id = int(link.get("sourceId") or link.get("source_id") or link.get("source"))
                target_id = int(link.get("targetId") or link.get("target_id") or link.get("target"))

                if link_type in ("feature_actor_relation", "feature_actor"):
                    await self._assert_leaf_feature(project_id, source_id, session)
                    check = await session.execute(
                        select(feature_actor_table).where(
                            feature_actor_table.c.feature_id == source_id,
                            feature_actor_table.c.actor_id == target_id,
                        )
                    )
                    if check.first():
                        raise PatchValidationError(
                            f"feature (id={source_id}) 与 actor (id={target_id}) 已存在关联关系"
                        )
                elif link_type in ("flow_feature_relation", "flow_feature"):
                    # P4: enforce direction — source=flow, target=feature
                    if not await self._entity_exists(project_id, "flow", source_id, session):
                        raise PatchValidationError(f"flow (id={source_id}) 不存在")
                    if not await self._entity_exists(project_id, "feature", target_id, session):
                        raise PatchValidationError(f"feature (id={target_id}) 不存在")
                    from backend.database.model import flow_feature_table
                    check = await session.execute(
                        select(flow_feature_table).where(
                            flow_feature_table.c.flow_id == source_id,
                            flow_feature_table.c.feature_id == target_id,
                        )
                    )
                    if check.first():
                        raise PatchValidationError(
                            f"flow (id={source_id}) 与 feature (id={target_id}) 已存在关联关系"
                        )

        if "addNodes" in patch:
            # P4: validate total count of business_object_attribute nodes (1-3)
            attr_count = sum(
                1 for n in patch.get("addNodes", [])
                if n.get("kind") == "business_object_attribute"
            )
            if attr_count > 0 and (attr_count < 1 or attr_count > 3):
                raise PatchValidationError(
                    f"business_object_attribute 数量为 {attr_count}，允许范围 1-3"
                )

            # Track names within this patch to detect intra-patch duplicates
            seen_attr_names = set()
            for node in patch.get("addNodes", []):
                kind = node.get("kind")
                if kind == "business_object_attribute":
                    name = node.get("name", "")
                    if not name or not name.strip():
                        raise PatchValidationError("business_object_attribute 属性名不能为空")
                    if name in seen_attr_names:
                        raise PatchValidationError(
                            f"business_object_attribute 属性名 '{name}' 在同一 patch 中重复"
                        )
                    seen_attr_names.add(name)
                    data_type = (node.get("data_type") or node.get("type") or "string").lower()
                    if data_type not in VALID_ATTRIBUTE_TYPES:
                        raise PatchValidationError(
                            f"business_object_attribute 类型 '{data_type}' 不在允许集合 {VALID_ATTRIBUTE_TYPES} 中"
                        )
                    bo_id = int(node.get("business_object_id") or node.get("businessObjectId") or 0)
                    if not await self._entity_exists(project_id, "business_object", bo_id, session):
                        raise PatchValidationError(f"business_object (id={bo_id}) 不存在")
                    from backend.database.model import BusinessObjectAttributeModel
                    dup_check = await session.execute(
                        select(BusinessObjectAttributeModel.id).where(
                            BusinessObjectAttributeModel.business_object_id == bo_id,
                            BusinessObjectAttributeModel.name == name,
                        )
                    )
                    if dup_check.first():
                        raise PatchValidationError(
                            f"business_object (id={bo_id}) 已存在名为 '{name}' 的属性"
                        )

    # ---- Full validation ----

    async def validate(
        self,
        project_id: int,
        issue_code: str,
        patch: dict,
        session,
    ) -> dict:
        """Run all three validation layers.

        Returns a validation report dict.
        """
        report = {"valid": True, "errors": [], "warnings": []}

        try:
            self.validate_structure(patch)
        except PatchValidationError as e:
            report["valid"] = False
            report["errors"].append(f"结构校验失败: {e}")
            return report

        try:
            await self.validate_references(project_id, patch, session)
        except PatchValidationError as e:
            report["valid"] = False
            report["errors"].append(f"引用校验失败: {e}")
            return report

        try:
            await self.validate_domain(project_id, issue_code, patch, session)
        except PatchValidationError as e:
            report["valid"] = False
            report["errors"].append(f"领域校验失败: {e}")
            return report

        return report

    # ---- Helpers ----

    @staticmethod
    async def _entity_exists(project_id: int, kind: str, entity_id: int, session) -> bool:
        if kind == "scope":
            # ScopeModel has no project_id — verify through FeatureModel
            res = await session.execute(
                select(ScopeModel.id).join(FeatureModel, ScopeModel.feature_id == FeatureModel.id)
                .where(ScopeModel.id == entity_id, FeatureModel.project_id == project_id)
            )
            return res.scalar_one_or_none() is not None

        model_map = {
            "actor": ActorModel,
            "feature": FeatureModel,
            "flow": FlowModel,
            "business_object": BusinessObjectModel,
            "scenario": ScenarioModel,
        }
        model = model_map.get(kind)
        if model is None:
            return False
        res = await session.execute(
            select(model.id).where(model.id == entity_id, model.project_id == project_id)
        )
        return res.scalar_one_or_none() is not None

    @staticmethod
    async def _assert_leaf_feature(project_id: int, feature_id: int, session) -> None:
        from backend.database.model import FeatureRelationModel
        # A leaf feature has no children
        child_res = await session.execute(
            select(FeatureRelationModel.id).where(
                FeatureRelationModel.parent_feature_id == feature_id
            )
        )
        if child_res.first():
            raise PatchValidationError(f"feature (id={feature_id}) 不是叶子功能")
