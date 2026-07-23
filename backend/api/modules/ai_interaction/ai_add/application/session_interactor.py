import logging
from sqlalchemy import select

from backend.core.llm_protected_inputs import collect_protected_texts
from backend.database.model import AIAddSessionModel, ProjectModel

logger = logging.getLogger(__name__)


class AIAddSessionInteractor:
    def __init__(self, strategy_registry):
        self._strategy_registry = strategy_registry

    @staticmethod
    async def _get_session_or_raise(session_id: int, session):
        """Load AIAddSessionModel by id, raise ValueError if not found."""
        from backend.database.model import AIAddSessionModel
        result = await session.execute(
            select(AIAddSessionModel).where(AIAddSessionModel.id == session_id)
        )
        db_session = result.scalar_one_or_none()
        if db_session is None:
            raise ValueError("session_not_found")
        return db_session

    async def get_session(self, session_id: int, session) -> dict:
        """Get session details by ID."""
        from backend.database.model import AIAddSessionModel, ProjectModel

        db_session = await self._get_session_or_raise(session_id, session)

        project_public_id = (await session.execute(
            select(ProjectModel.public_id).where(ProjectModel.id == db_session.project_id)
        )).scalar_one()

        return {
            "session_id": db_session.id,
            "project_id": project_public_id,
            "target_type": db_session.target_type,
            "anchor_payload": db_session.anchor_payload,
            "status": db_session.status,
            "summary_payload": db_session.summary_payload,
            "ready_to_generate": db_session.ready_to_generate,
            "created_at": db_session.created_at.isoformat() if db_session.created_at else None,
            "updated_at": db_session.updated_at.isoformat() if db_session.updated_at else None,
        }

    async def get_session_messages(self, session_id: int, session) -> list[dict]:
        """Get all messages for a session, ordered by creation time."""
        from backend.database.model import AIAddMessageModel

        result = await session.execute(
            select(AIAddMessageModel)
            .where(AIAddMessageModel.session_id == session_id)
            .order_by(AIAddMessageModel.created_at)
        )
        messages = result.scalars().all()
        return [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "extra": m.extra,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ]

    async def append_user_message(
        self,
        session_id: int,
        content: str,
        db_session,
    ) -> dict:
        """
        Append a user message, run the interview strategy, return the assistant reply.
        """
        from backend.database.model import AIAddMessageModel

        # Load session
        ai_session = await self._get_session_or_raise(session_id, db_session)

        if ai_session.status != "active":
            raise ValueError(f"session_not_active: status={ai_session.status}")

        # Save user message
        user_msg = AIAddMessageModel(
            session_id=session_id,
            role="user",
            content=content,
        )
        db_session.add(user_msg)
        await db_session.flush()

        # Get strategy
        strategy = self._strategy_registry.get(ai_session.target_type)

        # Load project context (only what the strategy needs)
        project_context = await self._load_context(
            ai_session.project_id,
            strategy.required_context,
            db_session,
        )
        protected_inputs = collect_protected_texts(
            project_context,
            ai_session.anchor_payload,
            ai_session.summary_payload,
            content,
        )

        # Build llm_call_chat function the strategy can use
        llm_handler = self._get_llm_handler()
        async def llm_call_chat(messages: list[dict], response_format: dict | None = None) -> str | None:
            return await llm_handler.call_chat(
                messages=messages,
                response_format=response_format,
                protected_inputs=protected_inputs,
            )

        # Build query for references retrieval
        query_parts = [ai_session.target_type, content]
        if ai_session.anchor_payload:
            query_parts.append(str(ai_session.anchor_payload))
        if ai_session.summary_payload and isinstance(ai_session.summary_payload, dict):
            known_facts = ai_session.summary_payload.get("known_facts")
            if known_facts:
                query_parts.append(str(known_facts))
        combined_query = " ".join(query_parts)

        from backend.services.knowledge.context_builder import KnowledgeContextBuilder
        knowledge_context = await KnowledgeContextBuilder.build(
            project_id=ai_session.project_id,
            purpose="ai_add_interview",
            query=combined_query,
            token_budget=3000,
            session=db_session,
        )
        protected_inputs += collect_protected_texts(knowledge_context)

        # Execute strategy
        import inspect
        sig = inspect.signature(strategy.interview)
        has_knowledge_context = (
            "knowledge_context" in sig.parameters
            or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
        )

        if has_knowledge_context:
            result = await strategy.interview(
                project_context=project_context,
                anchor=ai_session.anchor_payload,
                current_summary=ai_session.summary_payload,
                latest_user_message=content,
                llm_call_chat=llm_call_chat,
                knowledge_context=knowledge_context,
            )
        else:
            result = await strategy.interview(
                project_context=project_context,
                anchor=ai_session.anchor_payload,
                current_summary=ai_session.summary_payload,
                latest_user_message=content,
                llm_call_chat=llm_call_chat,
            )

        assistant_message = result.get("assistant_message", "")
        is_ready = bool(result.get("is_ready_to_generate", False))
        summary = result.get("summary", {})

        # Save assistant message
        assistant_msg = AIAddMessageModel(
            session_id=session_id,
            role="assistant",
            content=assistant_message,
        )
        db_session.add(assistant_msg)

        # Update session
        ai_session.summary_payload = summary
        ai_session.ready_to_generate = is_ready
        if is_ready:
            ai_session.status = "ready"

        logger.info(
            "AI add session message  session_id=%s  target_type=%s  ready=%s  round=%s",
            session_id, ai_session.target_type, is_ready,
            summary.get("round_count", "?"),
        )

        await db_session.flush()

        return {
            "session_id": session_id,
            "assistant_message": assistant_message,
            "is_ready_to_generate": is_ready,
            "summary": summary,
        }

    async def _load_context(
        self,
        project_id: int,
        required_context: list[str],
        session,
    ) -> dict:
        """Load project context sections as declared by the strategy."""
        from .session_creator import AIAddSessionCreator
        context = {}
        for key in required_context:
            loader = AIAddSessionCreator._CONTEXT_LOADERS.get(key)
            if loader is not None:
                context[key] = await loader(project_id, session)
        return context

    @staticmethod
    def _get_llm_handler():
        """Lazy import to avoid circular dependency."""
        from backend.services.llm_handler_service import LLMHandler
        return LLMHandler()
