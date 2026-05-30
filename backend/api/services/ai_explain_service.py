"""
AI Explain Service — stateless Q&A over project data.

Each call is independent: the user provides a question and a scope (node /
projection / workspace), the service loads the relevant project context as
formatted text, and calls the LLM to answer.

No sessions, no drafts, no persistence.
"""

from __future__ import annotations

import logging
from sqlalchemy import select

from backend.api.services.ai_explain_context import (
    NODE_LOADERS,
    _load_projection_context,
    _load_workspace_context,
)

logger = logging.getLogger(__name__)


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
            scope_label = f"阶段: {stage}"

        elif scope_kind == "workspace":
            context_text, objects_loaded = await _load_workspace_context(project_id, db_session)
            scope_label = "整个系统空间"

        else:
            raise ValueError(f"unsupported_scope_kind: {scope_kind}")

        # Build system prompt
        system_prompt = (
            f"# 角色\n"
            f"你是项目「{project.name}」的需求分析专家，负责回答用户关于项目的疑问。\n\n"
            f"# 回答规则\n"
            f"1. 只基于以下提供的项目信息回答，不要假设不存在的信息。\n"
            f"2. 如果信息不足，直接说项目中没有相关信息。\n"
            f"3. 回答时引用具体的对象名称和 ID，让用户知道信息来源。\n"
            f"4. 回答简洁，直接回答问题后可补充相关上下文。\n\n"
            f"# 项目需求概述\n"
            f"{project.user_requirements or '（无需求描述）'}\n\n"
            f"# 当前上下文范围：{scope_label}\n"
            f"{context_text}"
        )

        llm = self._get_llm_handler()
        answer = await llm.call_chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ])

        logger.info(
            "AI explain  project_id=%s  scope_kind=%s  scope_label=%s",
            project_id, scope_kind, scope_label,
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
            return f"{target_type}:{target_id}（已删除）"
        return f"{obj.name} ({target_type}:{target_id})"

    @staticmethod
    def _get_llm_handler():
        """Lazy import to avoid circular dependency."""
        from backend.services.LLM_service import LLMHandler
        return LLMHandler()
