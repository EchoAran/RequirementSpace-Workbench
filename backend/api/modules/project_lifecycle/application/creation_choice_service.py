import asyncio
import hashlib
import json
import logging
import time
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.modules.project_lifecycle.application.blank_service import BlankProjectService
from backend.api.modules.decision_workflow.public import (
    GenerationCandidate,
    CandidateContext,
    GenerationChoiceSettings,
    get_generation_choice_applier,
    _build_choice_group_response,
    BaseGenerationChoiceAdapter,
    run_candidate_generation,
    ChoiceActionResponse,
    GenerativeDraftStore,
)
from backend.api.modules.project_lifecycle.application.creation_service import ProjectCreationService
from backend.database.model import ChoiceGroupModel, ChoiceModel

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# ProjectCreationChoiceAdapter
# ═══════════════════════════════════════════════════════════════════

class ProjectCreationChoiceAdapter(BaseGenerationChoiceAdapter):
    """Adapter that generates multiple complete project draft candidates.

    Each candidate calls the existing _generate_preview() once, so
    N candidates make N LLM calls (balanced/comprehensive/minimal…).
    """

    generation_type = "project_creation"

    @property
    def _service(self):
        from backend.api.modules.project_lifecycle.ports import get_project_creation_service
        return get_project_creation_service()

    async def generate_candidate(self, context: CandidateContext) -> GenerationCandidate:
        """Generate one complete project draft candidate.

        The strategy hint is injected into the prompt via user_feedback so
        existing generators do not require signature changes.
        """
        # Build a strategy-aware user_feedback
        strategy_hint = f"请按 {context.strategy} 风格生成此项目草稿。"
        feedback = context.user_feedback or ""
        combined_feedback = f"{strategy_hint}\n{feedback}".strip()

        # Call the existing preview generator (it internally calls
        # _generate_project_preview + _generate_actor_and_feature_previews)
        draft_payload, response_payload = (
            await self._service._generate_preview(
                user_requirements=context.target.get("user_requirements", "")
                if context.target else "",
                user_feedback=combined_feedback,
                knowledge_context=context.target.get("knowledge_context")
                if context.target else None,
            )
        )

        # Add knowledge_workspace_id to draft_payload so it gets bound upon choice acceptance
        if context.target and context.target.get("knowledge_workspace_id"):
            draft_payload["knowledge_workspace_id"] = context.target.get("knowledge_workspace_id")

        title = self._make_title(context.strategy, response_payload)
        project_preview = response_payload.get("project_preview", {})
        actors = response_payload.get("actors", [])
        features = response_payload.get("features", [])

        return GenerationCandidate(
            title=title,
            rationale=f"按 {context.strategy} 策略生成的项目草稿",
            payload=draft_payload,
            preview={
                "project_name": project_preview.get("project_name", ""),
                "project_description": project_preview.get("project_description", ""),
                "actor_count": len(actors),
                "actors": [a.get("actor_name", "") for a in actors],
                "feature_count": len(features),
                "features": [f.get("feature_name", "") for f in features],
            },
            draft_type="project_creation",
            apply_mode="draft_payload",
            comparison_summary=self._make_comparison_summary(
                context.strategy, project_preview, actors, features,
            ),
            apply_behavior="overwrite",
            apply_behavior_description="此方案将基于候选创建新项目",
        )

    async def apply_candidate(self, payload: dict, session: AsyncSession, **kwargs) -> dict:
        """Persist the payload to real ProjectModel / ActorModel / FeatureModel."""
        project_id = kwargs.get("project_id")
        owner_user_id = kwargs.get("owner_user_id")
        if project_id is not None:
            project = await self._service._apply_project_creation_draft_to_existing_project(
                project_id=project_id,
                draft=payload,
                session=session,
            )
        else:
            project = await self._service._persist_project_creation_draft(
                draft=payload,
                owner_user_id=owner_user_id,
                session=session,
            )
        return {
            "project_id": project.public_id,
            "project_name": project.name,
            "project_description": project.description,
        }

    # ---- duplicate detection ----

    def is_duplicate(
        self, candidate: GenerationCandidate, existing: list[GenerationCandidate]
    ) -> bool:
        """Detect duplicates by comparing project name + actor names + feature names."""
        def _key(c: GenerationCandidate) -> tuple:
            p = c.payload or {}
            pp = p.get("project_preview", {}) or {}
            actors = frozenset(
                a.get("actor_name", "") for a in (p.get("actors") or [])
            )
            features = frozenset(
                f.get("feature_name", "") for f in (p.get("features") or [])
            )
            return (pp.get("project_name", ""), actors, features)

        c_key = _key(candidate)
        return any(_key(e) == c_key for e in existing)

    # ---- helpers ----

    @staticmethod
    def _make_title(strategy: str, response: dict) -> str:
        names = {
            "balanced": "均衡方案",
            "comprehensive": "全面方案",
            "minimal": "精简方案",
            "risk_averse": "保守方案",
            "workflow_first": "流程优先方案",
        }
        suffix = names.get(strategy, f"{strategy}方案")
        proj_name = response.get("project_preview", {}).get("project_name", "")
        return f"{proj_name} — {suffix}" if proj_name else suffix

    @staticmethod
    def _make_comparison_summary(
        strategy: str,
        project_preview: dict,
        actors: list[dict],
        features: list[dict],
    ) -> str:
        descriptions = {
            "balanced": "功能与复杂度均衡",
            "comprehensive": "功能全面、覆盖完整",
            "minimal": "最小可用、快速启动",
            "risk_averse": "保守设计、风险可控",
            "workflow_first": "流程驱动、步骤清晰",
        }
        desc = descriptions.get(strategy, strategy)
        actor_names = ", ".join(a.get("actor_name", "") for a in actors[:3])
        return (
            f"{desc}：{len(actors)} 名参与者（{actor_names}），"
            f"{len(features)} 项功能"
        )


# ═══════════════════════════════════════════════════════════════════
# ProjectCreationChoiceGroupService
# ═══════════════════════════════════════════════════════════════════

ONBOARDING_DRAFT_TYPE = "project_creation_choice_group"


class ProjectCreationChoiceGroupService:
    """Manages choice groups stored in GenerativeDraftModel during onboarding.

    Since choice_groups.project_id cannot be null yet, we use the
    GenerativeDraftModel as temporary storage until Phase 6 unification.
    """

    def __init__(self):
        self._settings = GenerationChoiceSettings.from_env()
        self._adapter = ProjectCreationChoiceAdapter()
        self._blank_project_service = BlankProjectService()
        # Register applier for project_creation if not already done
        applier = get_generation_choice_applier()
        if "project_creation" not in applier._adapter_classes:
            applier.register("project_creation", ProjectCreationChoiceAdapter)

    # ── Public API ──────────────────────────────────────────────

    async def create_choice_group(
        self,
        user_requirements: str,
        owner_user_id: int,
        candidate_count: int | None = None,
        user_feedback: str | None = None,
        session: AsyncSession | None = None,
        knowledge_workspace_id: str | None = None,
    ) -> dict:
        """Generate N project draft candidates and store as a choice group draft."""
        config = self._settings.with_overrides(candidate_count)
        group_id = f"pcg_{uuid4().hex[:12]}"

        # 1. Retrieve knowledge base context if workspace is active and belongs to user
        knowledge_context = None
        from backend.core.config import KNOWLEDGE_BASE_ENABLED
        if knowledge_workspace_id and KNOWLEDGE_BASE_ENABLED and session:
            from backend.database.model import KnowledgeWorkspaceModel
            from sqlalchemy import select
            from fastapi import HTTPException

            ws_res = await session.execute(
                select(KnowledgeWorkspaceModel).where(KnowledgeWorkspaceModel.public_id == knowledge_workspace_id)
            )
            ws = ws_res.scalar_one_or_none()
            if not ws:
                raise HTTPException(status_code=404, detail="workspace_not_found")
            if ws.owner_user_id != owner_user_id:
                raise HTTPException(status_code=403, detail="forbidden")
            if ws.status != "active":
                raise HTTPException(status_code=400, detail="workspace_inactive")

            # Construct combined query for context retrieval
            query_parts = [user_requirements]
            if user_feedback:
                query_parts.append(user_feedback)
            query_parts.append("生成项目名称、项目描述、参与者、功能树、业务边界")
            combined_query = " ".join(query_parts)

            from backend.services.knowledge.context_builder import KnowledgeContextBuilder
            knowledge_context = await KnowledgeContextBuilder.build(
                workspace_id=ws.id,
                purpose="project_creation",
                query=combined_query,
                token_budget=4000,
                session=session
            )

        # Prepare context and run concurrent generation
        base_ctx = CandidateContext(
            index=0,
            strategy="balanced",
            user_feedback=user_feedback,
            target={
                "user_requirements": user_requirements,
                "knowledge_context": knowledge_context,
                "knowledge_workspace_id": knowledge_workspace_id,
            },
            project_id=None,
        )
        result = await run_candidate_generation(
            count=config.candidate_count,
            max_concurrency=config.max_concurrency,
            timeout_seconds=config.timeout_seconds,
            generate_one=self._adapter.generate_candidate,
            base_context=base_ctx,
        )

        # Dedup
        deduped = []
        for c in result.candidates:
            if not self._adapter.is_duplicate(c, deduped):
                deduped.append(c)

        is_partial_failure = len(deduped) < config.partial_success_min
        group_status = "failed" if is_partial_failure else "open"

        # Build status_detail
        status_detail = {}
        if result.errors:
            status_detail["errors"] = [
                {"index": e.index, "strategy": e.strategy,
                 "error_type": e.error_type, "message": e.message}
                for e in result.errors
            ]
            status_detail["error_summary"] = (
                f"{result.total_count} 个候选已生成，"
                f"其中 {result.success_count} 个成功，{result.failure_count} 个失败"
            )
        if len(deduped) > 1:
            status_detail["comparison_summary"] = " | ".join(
                f"{c.title}: {c.comparison_summary}" for c in deduped
            )

        # Build choices list
        choices = []
        for i, c in enumerate(deduped):
            choice = {
                "id": f"pcc_{group_id}_{i}",
                "title": c.title,
                "rationale": c.rationale,
                "status": "candidate",
                "draft_type": "project_creation",
                "apply_mode": "draft_payload",
                "payload": c.payload,
                "preview": c.preview,
                "score": c.score,
                "comparison_summary": c.comparison_summary,
                "apply_behavior": c.apply_behavior,
                "apply_behavior_description": c.apply_behavior_description,
            }
            choices.append(choice)

        # Failed choices
        for e in result.errors:
            choices.append({
                "id": f"pcc_{group_id}_fail_{e.index}",
                "title": f"方案 {e.index+1} ({e.strategy})",
                "rationale": "",
                "status": "failed",
                "draft_type": "project_creation",
                "apply_mode": "draft_payload",
                "payload": {},
                "preview": {},
                "score": {},
                "comparison_summary": "",
                "error": {"error_type": e.error_type, "message": e.message},
            })

        # Compute context_hash
        context_hash = hashlib.sha256(
            json.dumps({"user_requirements": user_requirements}, sort_keys=True).encode()
        ).hexdigest()[:16]

        group_payload = {
            "choice_group_id": group_id,
            "status": group_status,
            "draft_type": ONBOARDING_DRAFT_TYPE,
            "generation_type": "project_creation",
            "user_requirements": user_requirements,
            "candidate_count": result.total_count,
            "success_count": len(deduped),
            "failure_count": result.failure_count,
            "status_detail": status_detail,
            "context_hash": context_hash,
            "choices": choices,
            "created_at": time.time(),
            "updated_at": time.time(),
        }

        # Save to GenerativeDraftModel
        if session:

            await GenerativeDraftStore.save_draft(
                project_id=None,
                draft_id=group_id,
                draft_type=ONBOARDING_DRAFT_TYPE,
                payload=group_payload,
                owner_user_id=owner_user_id,
                session=session,
            )

        return self._build_response(group_payload)

    async def get_choice_group(
        self, group_id: str, owner_user_id: int, session: AsyncSession | None = None
    ) -> dict | None:
        """Load a single onboarding choice group by id."""

        try:
            payload = await GenerativeDraftStore.get_draft(group_id, owner_user_id, session)
        except ValueError:
            return None
        if payload.get("draft_type") != ONBOARDING_DRAFT_TYPE:
            return None
        return self._build_response(payload)

    async def list_open_choice_groups(
        self, owner_user_id: int, session: AsyncSession | None = None
    ) -> list[dict]:
        """List all open onboarding choice groups."""
        from backend.database.model import GenerativeDraftModel
        result = await session.execute(
            select(GenerativeDraftModel)
            .where(
                GenerativeDraftModel.draft_type == ONBOARDING_DRAFT_TYPE,
                GenerativeDraftModel.owner_user_id == owner_user_id
            )
        )
        groups = []
        for draft in result.scalars().all():
            payload = draft.payload
            if payload.get("status") == "open":
                groups.append(self._build_response(payload))
        return groups

    async def accept_choice(
        self,
        group_id: str,
        choice_id: str,
        owner_user_id: int,
        session: AsyncSession | None = None,
    ) -> dict:
        """Accept a choice from an onboarding choice group.

        1. Load the group
        2. Find the choice
        3. Call _persist_project_creation_draft to create the real project
        4. Mark choice accepted, siblings rejected, group resolved
        5. Return project info
        """

        payload = await GenerativeDraftStore.get_draft(group_id, owner_user_id, session)
        if payload.get("draft_type") != ONBOARDING_DRAFT_TYPE:
            raise ValueError("invalid_onboarding_draft_type")
        if payload.get("status") != "open":
            raise ValueError("choice_group_not_open")

        # Find the choice
        target_choice = None
        for c in payload.get("choices", []):
            if c["id"] == choice_id:
                target_choice = c
                break
        if not target_choice:
            raise ValueError("choice_not_found")
        if target_choice.get("status") != "candidate":
            raise ValueError("choice_not_candidate")

        # Persist the project
        service = ProjectCreationService()
        project = await service._persist_project_creation_draft(
            draft=target_choice["payload"],
            owner_user_id=owner_user_id,
            session=session,
        )

        # Confirm & bind workspace documents/chunks to the new project
        workspace_public_id = target_choice["payload"].get("knowledge_workspace_id")
        if workspace_public_id:
            from backend.services.knowledge.workspace import KnowledgeWorkspaceService
            await KnowledgeWorkspaceService.bind_workspace_to_project(
                session=session,
                workspace_public_id=workspace_public_id,
                project_id=project.id,
                owner_user_id=owner_user_id,
            )

        # Update group state
        payload["status"] = "resolved"
        for c in payload.get("choices", []):
            if c["id"] == choice_id:
                c["status"] = "accepted"
            else:
                c["status"] = "rejected"
        payload["updated_at"] = time.time()
        payload["resolved_project_id"] = project.public_id

        # Save updated group
        await GenerativeDraftStore.save_draft(
            project_id=None,
            draft_id=group_id,
            draft_type=ONBOARDING_DRAFT_TYPE,
            payload=payload,
            owner_user_id=owner_user_id,
            session=session,
        )

        return {
            "project_id": project.public_id,
            "project_name": project.name,
            "project_description": project.description,
            "message": "project_created",
        }

    async def discard_choice_group(
        self, group_id: str, owner_user_id: int, session: AsyncSession | None = None
    ) -> dict:
        """Discard an onboarding choice group without creating a project."""

        try:
            payload = await GenerativeDraftStore.get_draft(group_id, owner_user_id, session)
        except ValueError:
            raise ValueError("choice_group_not_found")

        payload["status"] = "discarded"
        for c in payload.get("choices", []):
            c["status"] = "discarded"
        payload["updated_at"] = time.time()

        await GenerativeDraftStore.save_draft(
            project_id=None,
            draft_id=group_id,
            draft_type=ONBOARDING_DRAFT_TYPE,
            payload=payload,
            owner_user_id=owner_user_id,
            session=session,
        )

        return {"message": "choice_group_discarded", "group_id": group_id}

    async def defer_choice_group(
        self,
        group_id: str,
        owner_user_id: int,
        session: AsyncSession | None = None,
    ) -> dict:

        try:
            payload = await GenerativeDraftStore.get_draft(group_id, owner_user_id, session)

        except ValueError:
            raise ValueError("choice_group_not_found")

        if payload.get("draft_type") != ONBOARDING_DRAFT_TYPE:
            raise ValueError("invalid_onboarding_draft_type")
        if payload.get("status") != "open":
            raise ValueError("choice_group_not_open")

        project_result = await self._blank_project_service.create_project(
            user_requirements=payload.get("user_requirements", ""),
            project_name=None,
            project_description=None,
            owner_user_id=owner_user_id,
            session=session,
        )
        project_id = project_result["project_id"]

        # Resolve the internal integer id from the projects table
        from backend.database.model import ProjectModel
        proj_stmt = select(ProjectModel.id).where(ProjectModel.public_id == project_id)
        proj_id_internal = (await session.execute(proj_stmt)).scalar_one()

        group = ChoiceGroupModel(
            project_id=proj_id_internal,
            status="open",
            selection_mode="single",
            generation_type="project_creation",
            target={
                "source": "onboarding_defer",
                "onboarding_choice_group_id": group_id,
            },
            context_hash=payload.get("context_hash"),
            origin_endpoint="/api/project_creation_choice_groups/defer",
            candidate_count=payload.get("candidate_count"),
            success_count=payload.get("success_count"),
            failure_count=payload.get("failure_count"),
            status_detail={
                **(payload.get("status_detail") or {}),
                "migrated_from_onboarding": True,
                "onboarding_choice_group_id": group_id,
            },
        )
        session.add(group)
        await session.flush()

        created_choices: list[ChoiceModel] = []
        for candidate in payload.get("choices", []):
            choice = ChoiceModel(
                choice_group_id=group.id,
                title=candidate.get("title", ""),
                rationale=candidate.get("rationale", ""),
                status=candidate.get("status", "candidate"),
                patch={},
                impact_preview=None,
                payload=candidate.get("payload") or {},
                draft_type=candidate.get("draft_type", "project_creation"),
                apply_mode=candidate.get("apply_mode", "draft_payload"),
                preview=candidate.get("preview") or {},
                score=candidate.get("score"),
                error=candidate.get("error"),
            )
            session.add(choice)
            created_choices.append(choice)

        await session.flush()

        payload["status"] = "deferred"
        payload["updated_at"] = time.time()
        payload["deferred_project_id"] = project_id
        payload["migrated_choice_group_id"] = group.id
        await GenerativeDraftStore.save_draft(
            project_id=None,
            draft_id=group_id,
            draft_type=ONBOARDING_DRAFT_TYPE,
            payload=payload,
            owner_user_id=owner_user_id,
            session=session,
        )

        migrated_group = _build_choice_group_response(group, created_choices)
        return {
            "project_id": project_result["project_id"],
            "project_name": project_result["project_name"],
            "project_description": project_result["project_description"],
            "choice_group": migrated_group,
            "message": "project_created_with_deferred_choice_group",
        }

    # ── Helpers ─────────────────────────────────────────────────

    @staticmethod
    def _build_response(payload: dict) -> dict:
        """Convert the stored payload dict into an API response."""
        return {
            "id": payload.get("choice_group_id", ""),
            "status": payload.get("status", "open"),
            "generation_type": payload.get("generation_type", "project_creation"),
            "user_requirements": payload.get("user_requirements", ""),
            "candidate_count": payload.get("candidate_count"),
            "success_count": payload.get("success_count"),
            "failure_count": payload.get("failure_count"),
            "status_detail": payload.get("status_detail"),
            "context_hash": payload.get("context_hash"),
            "created_at": payload.get("created_at"),
            "updated_at": payload.get("updated_at"),
            "resolved_project_id": payload.get("resolved_project_id"),
            "choices": [
                {
                    "id": c.get("id", ""),
                    "title": c.get("title", ""),
                    "rationale": c.get("rationale", ""),
                    "status": c.get("status", ""),
                    "draft_type": c.get("draft_type", "project_creation"),
                    "apply_mode": c.get("apply_mode", "draft_payload"),
                    "payload": c.get("payload", {}),
                    "preview": c.get("preview", {}),
                    "score": c.get("score"),
                    "comparison_summary": c.get("comparison_summary", ""),
                    "error": c.get("error"),
                }
                for c in payload.get("choices", [])
            ],
        }
