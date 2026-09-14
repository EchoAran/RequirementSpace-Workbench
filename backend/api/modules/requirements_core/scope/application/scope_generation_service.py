from uuid import uuid4

from sqlalchemy import select

from backend.core.generators.scopes_generator import (
    ScopesGenerator,
    ScopesGeneratorInput,
)
from backend.core.notifier import get_notifier
from backend.schemas import FeatureNode
from backend.services.binary_conversion_service import (
    BinaryConversionError,
    BinaryConversionService,
)

from .scope_generation_context import load_scope_generation_context


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
        branch_name: str | None = None,
        head_commit_id: str | None = None,
        *,
        workspace_id: int,
    ) -> dict:
        from backend.database.model import BranchWorkspaceModel, ProjectModel


        # 1. Update kano_status to generating and commit immediately
        ws_res = await session.execute(select(BranchWorkspaceModel).where(BranchWorkspaceModel.id == workspace_id))
        ws = ws_res.scalar_one_or_none()
        if ws is None:
            raise ValueError("project_not_found")
        ws.kano_status = "generating"

        await session.flush()
        await session.commit()

        try:
            draft_id = uuid4().hex

            draft_payload, response_payload = await self._generate_preview(
                project_id=project_id,
                user_feedback=None,
                session=session,
                workspace_id=workspace_id,
            )

            draft_payload["draft_id"] = draft_id
            draft_payload["branch_name"] = branch_name
            draft_payload["head_commit_id"] = head_commit_id
            response_payload["draft_id"] = draft_id
            response_payload["branch_name"] = branch_name
            response_payload["head_commit_id"] = head_commit_id

            from backend.api.modules.decision_workflow.public import GenerativeDraftStore
            await GenerativeDraftStore.save_draft(
                project_id=project_id,
                draft_id=draft_id,
                draft_type="scope",
                payload=draft_payload,
                owner_user_id=owner_user_id,
                session=session,
            )

            # 2. Re-acquire workspace/project to update state
            ws_res = await session.execute(select(BranchWorkspaceModel).where(BranchWorkspaceModel.id == workspace_id))
            ws = ws_res.scalar_one_or_none()
            if ws:
                ws.kano_status = "missing"

            await session.flush()

            return response_payload
        except Exception as err:
            # Re-acquire project/workspace to set failed state
            try:
                ws_res = await session.execute(select(BranchWorkspaceModel).where(BranchWorkspaceModel.id == workspace_id))
                ws = ws_res.scalar_one_or_none()
                if ws:
                    ws.kano_status = "failed"

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
                                                        workspace_id=draft["workspace_id"],
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
        branch_name: str | None = None,
        head_commit_id: str | None = None,
        *,
        workspace_id: int,
    ) -> dict:
        from backend.database.model import ProjectModel
        draft = await self._get_draft(draft_id, owner_user_id, session)
        project_id = draft["project_id"]

        draft_branch = draft.get("branch_name")
        if draft_branch and branch_name and draft_branch != branch_name:
            raise ValueError(f"draft_branch_mismatch: Draft created on branch '{draft_branch}' cannot be confirmed on '{branch_name}'")

        draft_commit = draft.get("head_commit_id")
        if draft_commit and head_commit_id and draft_commit != head_commit_id:
            raise ValueError("branch_drift_detected: Branch head commit has advanced since draft creation")

        result = await self._persist_scope_generation_draft(
            draft=draft,
            session=session,
            workspace_id=workspace_id,
        )
        await get_notifier().mark_stale(
            project_id=project_id,
            stages={"scope"},
            session=session,
            workspace_id=workspace_id,
        )

        from backend.database.model import BranchWorkspaceModel


        # Set kano_status to generated
        ws_res = await session.execute(select(BranchWorkspaceModel).where(BranchWorkspaceModel.id == workspace_id))
        ws = ws_res.scalar_one_or_none()
        if ws:
            ws.kano_status = "generated"

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
        workspace_id: int,
    ) -> tuple[dict, dict]:
        (
            user_requirements,
            feature_nodes,
            leaf_feature_nodes,
        ) = await self._load_project_context(
            project_id=project_id,
            session=session,
            workspace_id=workspace_id,
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
        workspace_id: int,
    ) -> tuple[str, list[FeatureNode], list[FeatureNode]]:
        return await load_scope_generation_context(project_id, session, workspace_id=workspace_id)

    def _normalize_generated_scopes(
        self,
        raw: dict,
        leaf_feature_nodes: list[FeatureNode],
    ) -> list[dict]:
        raw_scopes = raw.get("scopes", [])

        if not raw_scopes:
            raise ValueError("empty_scopes")

        leaf_feature_map = {
            feature.featureId: feature
            for feature in leaf_feature_nodes
        }
        leaf_feature_ids = set(leaf_feature_map.keys())

        scopes_by_feature_id: dict[int, dict] = {}

        for item in raw_scopes:
            if not isinstance(item, dict):
                continue

            raw_fid = item.get("feature_id", item.get("featureId"))
            fid = None
            if raw_fid is not None:
                try:
                    fid = int(raw_fid)
                except (ValueError, TypeError):
                    fid = None

            if fid not in leaf_feature_ids:
                fname = str(item.get("feature_name", item.get("feature", ""))).strip().lower()
                for lf in leaf_feature_nodes:
                    if lf.featureName.strip().lower() == fname:
                        fid = lf.featureId
                        break

            if fid not in leaf_feature_ids:
                continue

            if fid in scopes_by_feature_id:
                continue

            scope_status = item.get(
                "scope_status",
                item.get("scopeStatus", item.get("scope")),
            )
            if not scope_status or str(scope_status).lower() not in self._valid_scope_statuses:
                scope_status = "current"

            reason = str(item.get("reason", item.get("reasons", "")) or "").strip()
            if not reason:
                reason = f"根据需求分析纳入规划范围：{leaf_feature_map[fid].featureName}"

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

            scopes_by_feature_id[fid] = {
                "feature_id": fid,
                "scope_status": str(scope_status).lower(),
                "reason": reason,
                "positive_summary": positive_summary,
                "negative_summary": negative_summary,
                "positive_picture_base64": positive_picture_base64,
                "negative_picture_base64": negative_picture_base64,
                "kano_category": item.get("kano_category", item.get("kanoCategory")),
                "kano_category_name": item.get("kano_category_name", item.get("kanoCategoryName")),
            }

        # Auto-fill any missing leaf features so LLM omissions never cause scope_feature_mismatch
        for lf in leaf_feature_nodes:
            if lf.featureId not in scopes_by_feature_id:
                scopes_by_feature_id[lf.featureId] = {
                    "feature_id": lf.featureId,
                    "scope_status": "current",
                    "reason": f"默认纳入当前规划范围：{lf.featureName}",
                    "positive_summary": None,
                    "negative_summary": None,
                    "positive_picture_base64": None,
                    "negative_picture_base64": None,
                    "kano_category": "O",
                    "kano_category_name": "一维属性",
                }

        # Preserve order of leaf_feature_nodes
        return [scopes_by_feature_id[lf.featureId] for lf in leaf_feature_nodes]

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
        workspace_id: int,
    ) -> dict:
        from backend.database.model import FeatureModel, ScopeModel


        project_id = draft["project_id"]
        scopes = draft["scopes"]
        feature_ids = [
            item["feature_id"]
            for item in scopes
        ]

        stmt = select(ScopeModel).join(FeatureModel, ScopeModel.feature_id == FeatureModel.id).where(ScopeModel.feature_id.in_(feature_ids))
        stmt = stmt.where(FeatureModel.workspace_id == workspace_id)

        existing_result = await session.execute(stmt)
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
                    workspace_id=workspace_id,
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

            scope_model.workspace_id = workspace_id
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
