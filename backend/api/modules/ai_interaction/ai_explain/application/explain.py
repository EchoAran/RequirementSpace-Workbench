"""
AI Explain Service — stateless Q&A over project data.

Each call is independent: the user provides a question and a scope (node /
projection / workspace), the service loads the relevant project context as
formatted text, and calls the LLM to answer.

No sessions, no drafts, no persistence.
"""

from __future__ import annotations

import logging
import time
from sqlalchemy import select

from backend.api.modules.ai_interaction.ai_explain.application.context import (
    NODE_LOADERS,
    _load_projection_context,
    _load_workspace_context,
)
from backend.core.logging import get_logger, log_event, sanitize_message
from backend.core.logging.events import AI_EXPLAIN_COMPLETED, AI_EXPLAIN_FAILED
from backend.core.llm_protected_inputs import collect_protected_texts
from backend.core.localized_messages import localized_message
from .context_locale import localize_ai_explain_context

logger = get_logger(__name__)


class AIExplainService:
    """Stateless Q&A explanation service. One call per question."""

    async def explain(
        self,
        project_id: int,
        scope: dict,
        question: str,
        db_session,
    ) -> dict:
        """Answer a question within the given scope context."""
        start_time = time.perf_counter()
        if not question or not question.strip():
            raise ValueError("empty_question")

        # Load project (validate existence + get name/requirements)
        from backend.database.model import ProjectModel
        project = await db_session.get(ProjectModel, project_id)
        if project is None:
            raise ValueError("project_not_found")

        scope_kind = scope.get("kind", "")
        context_text = ""
        scope_label = ""
        objects_loaded: list[str] = []

        from backend.core.prompt_resolver import resolve_prompt, get_content_locale
        locale = get_content_locale()

        if scope_kind == "node":
            target_type = scope.get("target_type", "")
            target_id = scope.get("target_id")
            if not target_type or not target_id:
                raise ValueError("invalid_node_scope")
            loader = NODE_LOADERS.get(target_type)
            if loader is None:
                raise ValueError(f"unsupported_target_type: {target_type}")
            context_text, objects_loaded = await loader(project_id, target_id, db_session)
            scope_label = await self._get_node_label(target_type, target_id, db_session)

        elif scope_kind == "projection":
            stage = scope.get("stage", "what")
            context_text, objects_loaded = await _load_projection_context(project_id, stage, db_session)
            scope_label = localized_message("ai_explain_stage", stage=stage)

        elif scope_kind == "workspace":
            context_text, objects_loaded = await _load_workspace_context(project_id, db_session)
            scope_label = localized_message("ai_explain_workspace")

        else:
            raise ValueError(f"unsupported_scope_kind: {scope_kind}")

        context_text = localize_ai_explain_context(context_text, locale)

        # Build system prompt
        raw_prompt = resolve_prompt("explain", locale)
        default_reqs = localized_message("ai_explain_no_requirements")
        system_prompt = raw_prompt.format(
            project_name=project.name,
            user_requirements=project.user_requirements or default_reqs,
            scope_label=scope_label,
            context_text=context_text
        )

        llm = self._get_llm_handler()
        try:
            answer = await llm.call_chat(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question},
                ],
                protected_inputs=collect_protected_texts(
                    project.name,
                    project.user_requirements,
                    context_text,
                    question,
                ),
            )
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "domain",
                AI_EXPLAIN_FAILED,
                "AI explain failed",
                project_id=project_id,
                target_type=scope.get("target_type"),
                target_id=scope.get("target_id"),
                error_type=type(exc).__name__,
                error_message=sanitize_message(str(exc)),
                duration_ms=int((time.perf_counter() - start_time) * 1000),
            )
            raise

        log_event(
            logger,
            logging.INFO,
            "domain",
            AI_EXPLAIN_COMPLETED,
            "AI explain completed",
            project_id=project_id,
            target_type=scope.get("target_type"),
            target_id=scope.get("target_id"),
            duration_ms=int((time.perf_counter() - start_time) * 1000),
            scope_kind=scope_kind,
            object_count=len(objects_loaded),
        )

        return {
            "answer": answer or "抱歉，我暂时无法回答这个问题。",
            "context_summary": {
                "scope_label": scope_label,
                "objects_loaded": objects_loaded,
            },
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _get_node_label(target_type: str, target_id: int, db_session) -> str:
        """Get a human-readable label for a node scope."""
        from backend.database.model import ActorModel, FeatureModel, FlowModel, BusinessObjectModel

        model_map = {
            "actor": ActorModel,
            "feature": FeatureModel,
            "flow": FlowModel,
            "business_object": BusinessObjectModel,
        }
        model_cls = model_map.get(target_type)
        if model_cls is None:
            return f"{target_type}:{target_id}"

        obj = await db_session.get(model_cls, target_id)
        if obj is None:
            return localized_message(
                "ai_explain_deleted_node",
                label=f"{target_type}:{target_id}",
            )
        return f"{obj.name} ({target_type}:{target_id})"

    @staticmethod
    def _get_llm_handler():
        """Lazy import to avoid circular dependency."""
        from backend.services.llm_handler_service import LLMHandler
        return LLMHandler()
