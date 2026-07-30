from __future__ import annotations

import asyncio
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .shadow_validator import PreviewShadowValidator
from .shadow_merger import PreviewShadowMerger
from .shadow_project_creator import (
    build_project_snapshot,
    calculate_stable_snapshot_hash,
    remap_snapshot_to_pydantic,
)
from backend.database.database import AsyncSessionLocal
from backend.database.model import (
    ProjectModel,
    PreviewShadowDraftModel,
    beijing_now,
)
from backend.api.modules.project_lifecycle.public import ProjectDetailResponse
from backend.core.llm_context import current_llm_context, is_web_request_ctx, LLMRequestContext
from backend.core.locale import DEFAULT_LOCALE, ContentLocaleSource, SupportedLocale


class PreviewShadowConvergenceService:
    def __init__(self) -> None:
        self.validator = PreviewShadowValidator()
        self.gate_evaluator = self.validator.gate_evaluator

    @property
    def _prototype_generation_service(self):
        from backend.api.modules.preview_convergence.ports import get_prototype_generation_service
        return get_prototype_generation_service()

    async def _generate_scopes_for_features(
        self,
        scope_service,
        user_requirements: str,
        feature_nodes: list,
        leaf_feature_nodes: list,
        user_feedback: str = "",
        temp_feat_to_int: dict[str, int] = None,
    ) -> list[dict]:
        return await PreviewShadowMerger.generate_scopes_for_features(
            scope_service=scope_service,
            user_requirements=user_requirements,
            feature_nodes=feature_nodes,
            leaf_feature_nodes=leaf_feature_nodes,
            user_feedback=user_feedback,
            temp_feat_to_int=temp_feat_to_int,
        )

    async def _generate_shadow_patch(
        self,
        project_id: int,
        base_snapshot: dict,
        session: AsyncSession = None,
        feedback: str = "",
        draft_id: str = "",
    ) -> dict:
        return await PreviewShadowMerger.generate_shadow_patch(
            service=self,
            project_id=project_id,
            base_snapshot=base_snapshot,
            session=session,
            feedback=feedback,
            draft_id=draft_id,
        )

    def _apply_patch_to_snapshot(
        self, base_snapshot: dict, patch: dict
    ) -> tuple[dict, dict[str, int]]:
        return PreviewShadowMerger.apply_patch_to_snapshot(base_snapshot, patch)



    async def _update_progress(self, draft_id: str, progress: int, message: str) -> None:
        try:
            async with AsyncSessionLocal() as session:
                draft_res = await session.execute(
                    select(PreviewShadowDraftModel).where(PreviewShadowDraftModel.draft_id == draft_id)
                )
                draft = draft_res.scalar_one_or_none()
                if draft and draft.status == "generating":
                    progress_info = {
                        "progress": progress,
                        "message": message
                    }
                    draft.error_message = json.dumps(progress_info, ensure_ascii=False)
                    await session.commit()
        except Exception:
            pass

    async def converge_shadow_snapshot_task(
        self,
        project_id: int,
        draft_id: str,
        api_url: str | None = None,
        api_key: str | None = None,
        model_name: str | None = None,
        content_locale: SupportedLocale = DEFAULT_LOCALE.value,
        content_locale_source: ContentLocaleSource = "default",
    ) -> None:
        """
        Background AsyncIO task worker with isolated database session context.
        """
        prototype_generation_service = self._prototype_generation_service
        token_ctx, token_web = self._activate_llm_context(
            api_url=api_url,
            api_key=api_key,
            model_name=model_name,
            content_locale=content_locale,
            content_locale_source=content_locale_source,
        )

        try:
            await asyncio.sleep(0.5)  # Let parent request return safely
            draft_input = await self._load_convergence_input(project_id, draft_id)
            if draft_input is None:
                return

            try:
                artifacts = await self._build_convergence_artifacts(
                    project_id=project_id,
                    draft_id=draft_id,
                    prototype_generation_service=prototype_generation_service,
                    **draft_input,
                )
                await self._save_convergence_artifacts(draft_id, artifacts)
            except Exception as exc:
                import traceback
                await self._mark_convergence_failed(
                    draft_id,
                    exc,
                    traceback.format_exc(),
                )
        finally:
            if token_ctx is not None:
                current_llm_context.reset(token_ctx)
            if token_web is not None:
                is_web_request_ctx.reset(token_web)

    @staticmethod
    def _activate_llm_context(
        *,
        api_url: str | None,
        api_key: str | None,
        model_name: str | None,
        content_locale: SupportedLocale,
        content_locale_source: ContentLocaleSource,
    ):
        if not (api_url and api_key and model_name):
            return None, None
        context = LLMRequestContext(
            api_url=api_url,
            api_key=api_key,
            model_name=model_name,
            content_locale=content_locale,
            content_locale_source=content_locale_source,
        )
        return current_llm_context.set(context), is_web_request_ctx.set(True)

    @staticmethod
    async def _load_convergence_input(
        project_id: int,
        draft_id: str,
    ) -> dict | None:
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(PreviewShadowDraftModel).where(
                        PreviewShadowDraftModel.draft_id == draft_id
                    )
                )
                draft = result.scalar_one_or_none()
                if not draft:
                    return None
                project = await session.get(ProjectModel, project_id)
                feedback = ""
                prefix = "Regenerating draft with feedback: "
                if draft.error_message and draft.error_message.startswith(prefix):
                    feedback = draft.error_message[len(prefix):].strip()
                return {
                    "project_public_id": (
                        project.public_id if project else str(project_id)
                    ),
                    "base_snapshot": draft.base_snapshot_json,
                    "feedback": feedback,
                }
        except Exception:
            return None

    async def _build_convergence_artifacts(
        self,
        *,
        project_id: int,
        draft_id: str,
        project_public_id: str,
        base_snapshot: dict,
        feedback: str,
        prototype_generation_service,
    ) -> dict:
        await self._update_progress(draft_id, 5, "preview.full.loadingShadow")
        patch = await self._generate_shadow_patch(
            project_id=project_id,
            base_snapshot=base_snapshot,
            feedback=feedback,
            draft_id=draft_id,
        )
        await self._update_progress(draft_id, 85, "preview.full.progressAssembly")
        self.validator.validate_patch(patch, base_snapshot, project_public_id)
        shadow_snapshot, _ = self._apply_patch_to_snapshot(base_snapshot, patch)
        remapped_snapshot = remap_snapshot_to_pydantic(shadow_snapshot)
        shadow_detail = ProjectDetailResponse.model_validate(remapped_snapshot)

        await self._update_progress(draft_id, 90, "preview.full.progressAssembly")
        generator_input = prototype_generation_service._build_generator_input(
            detail=shadow_detail,
            gherkin_specs=[],
        )
        targets = prototype_generation_service._build_role_feature_targets(
            generator_input=generator_input,
            detail=shadow_detail,
        )
        pages = await prototype_generation_service._generate_pages(targets)
        first_page = pages[0]
        prototype_preview = {
            "prototypeId": 0,
            "projectId": project_public_id,
            "html": first_page["html"],
            "javascript": first_page["javascript"],
            "css": first_page["css"],
            "pages": pages,
            "source": "shadow_project",
            "status": "ready",
            "createdAt": beijing_now().isoformat(),
            "updatedAt": beijing_now().isoformat(),
            "shadowDraftId": draft_id,
        }
        return {
            "shadow_snapshot_hash": calculate_stable_snapshot_hash(
                shadow_snapshot
            ),
            "shadow_snapshot_json": remapped_snapshot,
            "patch_json": patch,
            "prototype_preview_json": prototype_preview,
        }

    @staticmethod
    async def _save_convergence_artifacts(
        draft_id: str,
        artifacts: dict,
    ) -> None:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(PreviewShadowDraftModel).where(
                    PreviewShadowDraftModel.draft_id == draft_id
                )
            )
            draft = result.scalar_one_or_none()
            if draft:
                draft.status = "ready"
                for field, value in artifacts.items():
                    setattr(draft, field, value)
                await session.commit()

    @staticmethod
    async def _mark_convergence_failed(
        draft_id: str,
        error: Exception,
        error_trace: str,
    ) -> None:
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(PreviewShadowDraftModel).where(
                        PreviewShadowDraftModel.draft_id == draft_id
                    )
                )
                draft = result.scalar_one_or_none()
                if draft:
                    draft.status = "failed"
                    draft.error_message = (
                        f"Convergence failed: {str(error)}\n{error_trace}"
                    )
                    await session.commit()
        except Exception:
            pass

    async def commit_shadow_draft(
        self,
        project_id: int,
        draft_id: str,
        session: AsyncSession,
    ) -> None:
        """
        Transactionally write a validated shadow patch back to the project.
        """
        from .shadow_commit import commit_shadow_draft

        await commit_shadow_draft(
            self,
            project_id,
            draft_id,
            session,
        )


    @staticmethod
    async def discard_shadow_draft(project_id: int, draft_id: str, session: AsyncSession) -> None:
        """
        Soft deletes the shadow draft by updating its status and timestamp.
        """
        draft_res = await session.execute(
            select(PreviewShadowDraftModel).where(
                PreviewShadowDraftModel.project_id == project_id,
                PreviewShadowDraftModel.draft_id == draft_id
            )
        )
        draft = draft_res.scalar_one_or_none()
        if not draft:
            raise ValueError("shadow_draft_not_found")
        
        draft.status = "discarded"
        draft.discarded_at = beijing_now()
