from uuid import uuid4

from sqlalchemy import select

from backend.api.modules.requirements_core.ports import get_notifier
from backend.core.generators.scopes_generator import (
    ScopesGenerator,
    ScopesGeneratorInput,
)
from backend.schemas import FeatureNode, ScopeNode, ScopeStatus
from backend.services.binary_conversion_service import (
    BinaryConversionError,
    BinaryConversionService,
)


class ScopeGenerationService:
    _valid_scope_statuses = {
        "CURRENT",
        "POSTPONED",
        "EXCLUDE",
        "current",
        "postponed",
        "exclude",
    }

    def __init__(self):
        self._scopes_generator = ScopesGenerator()

    async def create_draft(
        self,
        project_id: int,
        owner_user_id: int,
        session,
    ) -> dict:
        from backend.database.model import ProjectModel
        # 1. Update project kano_status to generating and commit immediately
        project_res = await session.execute(
            select(ProjectModel).where(
                ProjectModel.id == project_id,
                ProjectModel.owner_user_id == owner_user_id,
            )
        )
        project = project_res.scalar_one_or_none()
        if project is None:
            raise ValueError("project_not_found")
        project.kano_status = "generating"
        await session.flush()
        await session.commit()

        try:
            draft_id = uuid4().hex

            draft_payload, response_payload = await self._generate_preview(
                project_id=project_id,
                user_feedback=None,
                session=session,
            )

            draft_payload["draft_id"] = draft_id
            response_payload["draft_id"] = draft_id

            from backend.api.modules.decision_workflow.public import GenerativeDraftStore
            await GenerativeDraftStore.save_draft(
                project_id=project_id,
                draft_id=draft_id,
                draft_type="scope",
                payload=draft_payload,
                owner_user_id=owner_user_id,
                session=session,
            )

            # 2. Re-acquire project to set draft_ready state
            project_res = await session.execute(
                select(ProjectModel).where(
                    ProjectModel.id == project_id,
                    ProjectModel.owner_user_id == owner_user_id,
                )
            )
            project = project_res.scalar_one()
            project.kano_status = "missing"
            await session.flush()

            return response_payload
        except Exception as err:
            # Re-acquire project under new transaction to set failed state
            try:
                project_res = await session.execute(
                    select(ProjectModel).where(
                        ProjectModel.id == project_id,
                        ProjectModel.owner_user_id == owner_user_id,
                    )
                )
                project = project_res.scalar_one_or_none()
                if project:
                    project.kano_status = "failed"
                    await session.flush()
                    await session.commit()
            except Exception:
                pass
            raise err

    async def regenerate_draft(
        self,
        draft_id: str,
        owner_user_id: int,
        user_feedback: str | None,
        session,
    ) -> dict:
        from backend.database.model import ProjectModel
        draft = await self._get_draft(draft_id, owner_user_id, session)
        project_id = draft["project_id"]

        # 1. Set project kano_status to generating
        project_res = await session.execute(
            select(ProjectModel).where(
                ProjectModel.id == project_id,
                ProjectModel.owner_user_id == owner_user_id,
            )
        )
        project = project_res.scalar_one_or_none()
        if project:
            project.kano_status = "generating"
            await session.flush()
            await session.commit()

        try:
            draft_payload, response_payload = await self._generate_preview(
                project_id=project_id,
                user_feedback=user_feedback,
                session=session,
            )

            draft_payload["draft_id"] = draft_id
            response_payload["draft_id"] = draft_id

            from backend.api.modules.decision_workflow.public import GenerativeDraftStore
            await GenerativeDraftStore.save_draft(
                project_id=project_id,
                draft_id=draft_id,
                draft_type="scope",
                payload=draft_payload,
                owner_user_id=owner_user_id,
                session=session,
            )

            # 2. Re-acquire to set draft_ready
            project_res = await session.execute(
                select(ProjectModel).where(
                    ProjectModel.id == project_id,
                    ProjectModel.owner_user_id == owner_user_id,
                )
            )
            project = project_res.scalar_one()
            project.kano_status = "missing"
            await session.flush()

            return response_payload
        except Exception as err:
            try:
                project_res = await session.execute(
                    select(ProjectModel).where(
                        ProjectModel.id == project_id,
                        ProjectModel.owner_user_id == owner_user_id,
                    )
                )
                project = project_res.scalar_one_or_none()
                if project:
                    project.kano_status = "failed"
                    await session.flush()
                    await session.commit()
            except Exception:
                pass
            raise err

    async def confirm_draft(
        self,
        draft_id: str,
        owner_user_id: int,
        session,
    ) -> dict:
        from backend.database.model import ProjectModel
        draft = await self._get_draft(draft_id, owner_user_id, session)
        project_id = draft["project_id"]

        result = await self._persist_scope_generation_draft(
            draft=draft,
            session=session,
        )
        await get_notifier().mark_stale(
            project_id=project_id,
            stages={"scope"},
            session=session,
        )

        # Set kano_status to generated
        project_res = await session.execute(
            select(ProjectModel).where(
                ProjectModel.id == project_id,
                ProjectModel.owner_user_id == owner_user_id,
            )
        )
        project = project_res.scalar_one_or_none()
        if project:
            project.kano_status = "generated"
            await session.flush()

        from backend.api.modules.decision_workflow.public import GenerativeDraftStore
        await GenerativeDraftStore.delete_draft(draft_id, owner_user_id, session)

        return result

    async def discard_draft(
        self,
        draft_id: str,
        owner_user_id: int,
        session,
    ) -> dict:
        from backend.database.model import ProjectModel
        try:
            draft = await self._get_draft(draft_id, owner_user_id, session)
            project_id = draft["project_id"]
            project_res = await session.execute(
                select(ProjectModel).where(
                    ProjectModel.id == project_id,
                    ProjectModel.owner_user_id == owner_user_id,
                )
            )
            project = project_res.scalar_one_or_none()
            if project:
                project.kano_status = "missing"
                await session.flush()
        except ValueError:
            pass

        from backend.api.modules.decision_workflow.public import GenerativeDraftStore
        await GenerativeDraftStore.delete_draft(draft_id, owner_user_id, session)

        return {
            "draft_id": draft_id,
            "message": "draft_discarded",
        }

    async def _get_draft(
        self,
        draft_id: str,
        owner_user_id: int,
        session,
    ) -> dict:
        from backend.api.modules.decision_workflow.public import GenerativeDraftStore
        return await GenerativeDraftStore.get_draft(draft_id, owner_user_id, session)

    async def _generate_preview(
        self,
        project_id: int,
        user_feedback: str | None,
        session,
    ) -> tuple[dict, dict]:
        (
            user_requirements,
            feature_nodes,
            leaf_feature_nodes,
        ) = await self._load_project_context(
            project_id=project_id,
            session=session,
        )

        raw = await self._scopes_generator.generate(
            ScopesGeneratorInput(
                user_requirements=user_requirements,
                features=feature_nodes,
                user_feedback=user_feedback,
            )
        )

        scopes = self._normalize_generated_scopes(
            raw=raw,
            leaf_feature_nodes=leaf_feature_nodes,
        )

        draft_payload = {
            "project_id": project_id,
            "scopes": scopes,
        }

        response_payload = self._build_response_payload(
            project_id=project_id,
            draft_payload=draft_payload,
            feature_nodes=leaf_feature_nodes,
        )

        return draft_payload, response_payload

    @staticmethod
    async def _load_project_context(
        project_id: int,
        session,
    ) -> tuple[str, list[FeatureNode], list[FeatureNode]]:
        from backend.database.model import (
            FeatureModel,
            FeatureRelationModel,
            ProjectModel,
            ScopeModel,
            feature_actor_table,
        )

        project_result = await session.execute(
            select(ProjectModel).where(
                ProjectModel.id == project_id,
            )
        )
        project = project_result.scalar_one_or_none()

        if project is None:
            raise ValueError("project_not_found")

        feature_result = await session.execute(
            select(FeatureModel).where(
                FeatureModel.project_id == project_id,
            )
        )
        feature_models = feature_result.scalars().all()

        if not feature_models:
            raise ValueError("empty_features")

        feature_id_set = {
            feature.id
            for feature in feature_models
        }

        relation_result = await session.execute(
            select(FeatureRelationModel).where(
                FeatureRelationModel.parent_feature_id.in_(
                    feature_id_set
                )
            )
        )
        relation_models = relation_result.scalars().all()

        feature_actor_result = await session.execute(
            select(
                feature_actor_table.c.feature_id,
                feature_actor_table.c.actor_id,
            ).where(
                feature_actor_table.c.feature_id.in_(
                    feature_id_set
                )
            )
        )
        feature_actor_rows = feature_actor_result.all()

        scope_result = await session.execute(
            select(ScopeModel).where(
                ScopeModel.feature_id.in_(feature_id_set)
            )
        )
        scope_models = scope_result.scalars().all()

        children_map: dict[int, list[int]] = {}
        parent_map: dict[int, int] = {}

        for relation in relation_models:
            children_map.setdefault(
                relation.parent_feature_id,
                [],
            ).append(relation.child_feature_id)

            parent_map[
                relation.child_feature_id
            ] = relation.parent_feature_id

        actor_ids_map: dict[int, list[int]] = {}

        for feature_id, actor_id in feature_actor_rows:
            actor_ids_map.setdefault(
                feature_id,
                [],
            ).append(actor_id)

        scope_node_map = {}

        for scope in scope_models:
            status_str = scope.status.upper()
            if status_str in ScopeStatus.__members__:
                scope_status = ScopeStatus[status_str]
            else:
                try:
                    scope_status = ScopeStatus(scope.status.lower())
                except ValueError:
                    continue

            scope_node_map[scope.feature_id] = ScopeNode(
                scopeId=scope.id,
                scopeStatus=scope_status,
                reason=scope.reason,
                positiveSummary=scope.positive_summary or None,
                negativeSummary=scope.negative_summary or None,
                positivePictureBase64=(
                    BinaryConversionService.bytes_to_base64(
                        scope.positive_picture
                    )
                    if scope.positive_picture is not None
                    else None
                ),
                negativePictureBase64=(
                    BinaryConversionService.bytes_to_base64(
                        scope.negative_picture
                    )
                    if scope.negative_picture is not None
                    else None
                ),
                kanoCategory=scope.kano_category,
                kanoCategoryName=scope.kano_category_name,
            )

        feature_nodes = [
            FeatureNode(
                featureId=feature.id,
                featureName=feature.name,
                featureDescription=feature.description,
                actorIds=actor_ids_map.get(feature.id, []),
                parentId=parent_map.get(feature.id),
                childrenIds=children_map.get(feature.id, []),
                scope=scope_node_map.get(feature.id),
            )
            for feature in feature_models
        ]

        leaf_feature_nodes = [
            feature
            for feature in feature_nodes
            if len(feature.childrenIds) == 0
        ]

        if not leaf_feature_nodes:
            raise ValueError("empty_leaf_features")

        return (
            project.user_requirements,
            feature_nodes,
            leaf_feature_nodes,
        )

    def _normalize_generated_scopes(
        self,
        raw: dict,
        leaf_feature_nodes: list[FeatureNode],
    ) -> list[dict]:
        raw_scopes = raw.get("scopes", [])

        if not raw_scopes:
            raise ValueError("empty_scopes")

        leaf_feature_ids = {
            feature.featureId
            for feature in leaf_feature_nodes
        }

        scope_feature_ids = [
            item.get("feature_id")
            for item in raw_scopes
        ]

        if len(set(scope_feature_ids)) != len(scope_feature_ids):
            raise ValueError("duplicate_scope_feature")

        if set(scope_feature_ids) != leaf_feature_ids:
            raise ValueError("scope_feature_mismatch")

        scopes = []

        for item in raw_scopes:
            feature_id = item.get("feature_id")
            scope_status = item.get(
                "scope_status",
                item.get("scopeStatus", item.get("scope")),
            )
            reason = item.get("reason", item.get("reasons", ""))
            positive_summary = item.get(
                "positive_summary",
                item.get("positiveSummary"),
            )
            negative_summary = item.get(
                "negative_summary",
                item.get("negativeSummary"),
            )
            positive_picture_base64 = item.get(
                "positive_picture_base64",
                item.get("positivePictureBase64"),
            )
            negative_picture_base64 = item.get(
                "negative_picture_base64",
                item.get("negativePictureBase64"),
            )

            if feature_id not in leaf_feature_ids:
                raise ValueError("invalid_feature_reference")

            if scope_status not in self._valid_scope_statuses:
                raise ValueError("invalid_scope_status")

            if not reason:
                raise ValueError("invalid_scope_payload")

            scopes.append(
                {
                    "feature_id": feature_id,
                    "scope_status": scope_status.lower(),
                    "reason": reason,
                    "positive_summary": positive_summary,
                    "negative_summary": negative_summary,
                    "positive_picture_base64": positive_picture_base64,
                    "negative_picture_base64": negative_picture_base64,
                    "kano_category": item.get("kano_category", item.get("kanoCategory")),
                    "kano_category_name": item.get("kano_category_name", item.get("kanoCategoryName")),
                }
            )

        return scopes

    @staticmethod
    def _build_response_payload(
        project_id: int,
        draft_payload: dict,
        feature_nodes: list[FeatureNode],
    ) -> dict:
        feature_name_map = {
            feature.featureId: feature.featureName
            for feature in feature_nodes
        }

        return {
            "project_id": project_id,
            "scopes": [
                {
                    "feature_id": item["feature_id"],
                    "feature_name": feature_name_map[item["feature_id"]],
                    "scope_status": item["scope_status"],
                    "reason": item["reason"],
                    "positive_summary": item.get("positive_summary"),
                    "negative_summary": item.get("negative_summary"),
                    "positive_picture_base64": item.get(
                        "positive_picture_base64"
                    ),
                    "negative_picture_base64": item.get(
                        "negative_picture_base64"
                    ),
                    "kano_category": item.get("kano_category"),
                    "kano_category_name": item.get("kano_category_name"),
                }
                for item in draft_payload["scopes"]
            ],
        }

    @staticmethod
    async def _persist_scope_generation_draft(
        draft: dict,
        session,
    ) -> dict:
        from backend.database.model import ScopeModel

        project_id = draft["project_id"]
        scopes = draft["scopes"]
        feature_ids = [
            item["feature_id"]
            for item in scopes
        ]

        existing_result = await session.execute(
            select(ScopeModel).where(
                ScopeModel.feature_id.in_(feature_ids)
            )
        )
        existing_scope_map = {
            scope.feature_id: scope
            for scope in existing_result.scalars().all()
        }

        for item in scopes:
            try:
                positive_picture = (
                    BinaryConversionService.base64_to_bytes(
                        item["positive_picture_base64"]
                    )
                    if item.get("positive_picture_base64")
                    else None
                )
                negative_picture = (
                    BinaryConversionService.base64_to_bytes(
                        item["negative_picture_base64"]
                    )
                    if item.get("negative_picture_base64")
                    else None
                )
            except BinaryConversionError as error:
                raise ValueError("invalid_picture_base64") from error

            scope_model = existing_scope_map.get(item["feature_id"])

            if scope_model is None:
                scope_model = ScopeModel(
                    feature_id=item["feature_id"],
                    status=item["scope_status"],
                    positive_summary=item.get("positive_summary") or "",
                    negative_summary=item.get("negative_summary") or "",
                    positive_picture=positive_picture,
                    negative_picture=negative_picture,
                    reason=item["reason"],
                    kano_category=item.get("kano_category"),
                    kano_category_name=item.get("kano_category_name"),
                    confirmation_status='ai_assumption',
                )
                session.add(scope_model)
                continue

            scope_model.status = item["scope_status"]
            scope_model.positive_summary = item.get("positive_summary") or ""
            scope_model.negative_summary = item.get("negative_summary") or ""
            scope_model.positive_picture = positive_picture
            scope_model.negative_picture = negative_picture
            scope_model.reason = item["reason"]
            scope_model.kano_category = item.get("kano_category")
            scope_model.kano_category_name = item.get("kano_category_name")

        await session.flush()

        return {
            "project_id": project_id,
            "scope_count": len(scopes),
            "message": "scopes_created",
        }
