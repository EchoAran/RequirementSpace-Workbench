"""
Service for managing AI-powered conversational single-object addition sessions.

Orchestrates the full lifecycle:
  1. create_session — create a new interview session with a target object type
  2. append_user_message — process user chat, get assistant reply via strategy
  3. generate_draft — convert the interview summary into a generative draft
  4. confirm_draft / discard_draft — finalize or cancel the draft

Phase 1 uses stub interview strategies and Phase 2 uses SingleObjectGenerators
for structured draft generation, backed by CRUD services for confirmation.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from uuid import uuid4

from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

BEIJING_TZ = ZoneInfo("Asia/Shanghai")


def _beijing_now() -> datetime:
    return datetime.now(BEIJING_TZ)

from sqlalchemy import select

from backend.api.modules.ai_interaction.ai_add.application.interview_strategy import (
    InterviewStrategyRegistry,
    create_default_registry,
)
from backend.api.modules.ai_interaction.ai_add.application.generator_registry import (
    SingleObjectGeneratorRegistry,
    create_default_generator_registry,
    EditGeneratorRegistry,
    create_default_edit_generator_registry,
)


class AIAddSessionService:
    """Manages AI-powered conversational single-object addition sessions."""

    def __init__(
        self,
        strategy_registry: InterviewStrategyRegistry | None = None,
        generator_registry: SingleObjectGeneratorRegistry | None = None,
        edit_generator_registry: EditGeneratorRegistry | None = None,
    ):
        self._strategy_registry = strategy_registry or create_default_registry()
        self._generator_registry = generator_registry or create_default_generator_registry()
        self._edit_generator_registry = edit_generator_registry or create_default_edit_generator_registry()

        from .session_creator import AIAddSessionCreator
        from .session_interactor import AIAddSessionInteractor
        from .session_draft_handler import AIAddDraftHandler
        self.creator = AIAddSessionCreator(self._strategy_registry)
        self.interactor = AIAddSessionInteractor(self._strategy_registry)
        self.draft_handler = AIAddDraftHandler(self)

    # ------------------------------------------------------------------
    # Context loaders — loads project data required by the strategy
    # ------------------------------------------------------------------
    _CONTEXT_LOADERS = {}

    @staticmethod
    async def _load_project_actors(project_id: int, session) -> list[dict]:
        from .session_creator import AIAddSessionCreator
        return await AIAddSessionCreator._load_project_actors(project_id, session)

    @staticmethod
    async def _load_project_feature_tree(project_id: int, session) -> list[dict]:
        from .session_creator import AIAddSessionCreator
        return await AIAddSessionCreator._load_project_feature_tree(project_id, session)

    @staticmethod
    async def _load_project_flows(project_id: int, session) -> list[dict]:
        from .session_creator import AIAddSessionCreator
        return await AIAddSessionCreator._load_project_flows(project_id, session)

    @staticmethod
    async def _load_project_business_objects(project_id: int, session) -> list[dict]:
        from .session_creator import AIAddSessionCreator
        return await AIAddSessionCreator._load_project_business_objects(project_id, session)

    _CONTEXT_LOADERS = {
        "actors": _load_project_actors,
        "features": _load_project_feature_tree,
        "flows": _load_project_flows,
        "business_objects": _load_project_business_objects,
    }

    # ------------------------------------------------------------------
    # Session CRUD
    # ------------------------------------------------------------------

    async def create_session(
        self,
        project_id: str,
        target_type: str,
        anchor: dict,
        session,
        owner_user_id: int,
    ) -> dict:
        """Create a new AI add session. Validates target_type and anchor references."""
        return await self.creator.create_session(
            project_id=project_id,
            target_type=target_type,
            anchor=anchor,
            session=session,
            owner_user_id=owner_user_id,
        )

    async def get_session(self, session_id: int, session) -> dict:
        """Get session details by ID."""
        return await self.interactor.get_session(session_id, session)

    async def get_session_messages(self, session_id: int, session) -> list[dict]:
        """Get all messages for a session, ordered by creation time."""
        return await self.interactor.get_session_messages(session_id, session)

    # ------------------------------------------------------------------
    # Core chat loop
    # ------------------------------------------------------------------

    async def append_user_message(
        self,
        session_id: int,
        content: str,
        db_session,
    ) -> dict:
        """
        Append a user message, run the interview strategy, return the assistant reply.
        """
        return await self.interactor.append_user_message(
            session_id=session_id,
            content=content,
            db_session=db_session,
        )

    # ------------------------------------------------------------------
    # Draft lifecycle — Phase 2: real SingleObjectGenerator + CRUD confirm
    # ------------------------------------------------------------------

    def _get_generator(self, target_type: str):
        """Return a generator instance — add or edit based on target_type prefix."""
        if target_type.startswith("edit_"):
            return self._edit_generator_registry.get(target_type)
        return self._generator_registry.get(target_type)

    async def generate_draft(self, session_id: int, db_session, owner_user_id: int) -> dict:
        """Generate a draft — dispatches to add or edit path based on target_type."""
        return await self.draft_handler.generate_draft(
            session_id=session_id, db_session=db_session, owner_user_id=owner_user_id
        )

    async def confirm_draft(self, draft_id: str, db_session, owner_user_id: int) -> dict:
        """Confirm a draft — dispatches to add or edit path based on target_type."""
        return await self.draft_handler.confirm_draft(
            draft_id=draft_id, db_session=db_session, owner_user_id=owner_user_id
        )

    async def discard_draft(self, draft_id: str, db_session, owner_user_id: int) -> dict:
        """Discard a draft without persisting."""
        return await self.draft_handler.discard_draft(
            draft_id=draft_id, db_session=db_session, owner_user_id=owner_user_id
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _load_context(
        self,
        project_id: int,
        required_context: list[str],
        session,
    ) -> dict:
        """Load project context sections as declared by the strategy."""
        context = {}
        for key in required_context:
            loader = self._CONTEXT_LOADERS.get(key)
            if loader is not None:
                context[key] = await loader(project_id, session)
        return context

    @staticmethod
    def _get_llm_handler():
        """Lazy import to avoid circular dependency."""
        from backend.services.llm_handler_service import LLMHandler
        return LLMHandler()

    @staticmethod
    def _validate_generated_object(target_type: str, raw: dict, project_context: dict) -> dict:
        from .session_draft_handler import AIAddDraftHandler
        return AIAddDraftHandler._validate_generated_object(target_type, raw, project_context)

    @staticmethod
    def _build_preview(target_type: str, validated: dict) -> dict:
        from .session_draft_handler import AIAddDraftHandler
        return AIAddDraftHandler._build_preview(target_type, validated)

    @staticmethod
    async def _pre_confirm_validation(target_type: str, generated: dict, project_id: int, db_session) -> None:
        from .session_draft_handler import AIAddDraftHandler
        await AIAddDraftHandler._pre_confirm_validation(target_type, generated, project_id, db_session)

    @staticmethod
    def _validate_edit_diff(base_type: str, diff: dict) -> None:
        from .session_draft_handler import AIAddDraftHandler
        AIAddDraftHandler._validate_edit_diff(base_type, diff)

    @staticmethod
    async def _validate_edit_references(base_type: str, diff: dict, project_id: int, db_session) -> None:
        from .session_draft_handler import AIAddDraftHandler
        await AIAddDraftHandler._validate_edit_references(base_type, diff, project_id, db_session)

    @staticmethod
    async def _load_original_object(base_type: str, anchor: dict, project_id: int, db_session) -> dict:
        from .session_draft_handler import AIAddDraftHandler
        return await AIAddDraftHandler._load_original_object(base_type, anchor, project_id, db_session)

    @staticmethod
    async def _validate_anchor_references(project_id: int, target_type: str, anchor: dict, session) -> None:
        from .session_draft_handler import AIAddDraftHandler
        await AIAddDraftHandler._validate_anchor_references(project_id, target_type, anchor, session)

    @staticmethod
    async def _get_session_or_raise(session_id: int, session):
        from .session_draft_handler import AIAddDraftHandler
        return await AIAddDraftHandler._get_session_or_raise(session_id, session)
