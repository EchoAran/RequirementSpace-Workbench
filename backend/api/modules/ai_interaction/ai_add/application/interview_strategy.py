"""
Interview strategies for AI-powered conversational single-object addition and edit.

Each strategy knows what questions to ask for a specific object type (actor,
feature, flow, business_object), when enough information has been gathered,
and how to produce a structured summary for downstream single-object generators.

Strategies utilize the current_summary payload to preserve multi-turn conversation
history and coordinate with the real LLM for robust slot-filling.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Coroutine

from backend.core.prompt_resolver import resolve_prompt
from backend.core.localized_messages import localized_message

logger = logging.getLogger(__name__)

def _localized_prompt(name: str, **values: object) -> str:
    prompt = resolve_prompt(name)
    for key, value in values.items():
        prompt = prompt.replace(f"{{{{{key}}}}}", str(value))
    return prompt


class BaseInterviewStrategy(ABC):
    """
    Abstract interview strategy for a single object type.

    Subclasses must set target_type and required_context, and implement
    interview() to produce the next assistant response.
    """

    target_type: str = ""
    required_context: list[str] = []

    @abstractmethod
    async def interview(
        self,
        project_context: dict,
        anchor: dict,
        current_summary: dict | None,
        latest_user_message: str,
        llm_call_chat: Callable[..., Coroutine[Any, Any, str | None]],
        knowledge_context: str | None = None,
    ) -> dict:
        """
        Process the latest user message and decide the next action.

        Args:
            project_context: Pre-loaded project data (controlled by required_context).
            anchor: Entry-point context from session creation.
            current_summary: The summary payload from the previous round (None for first round).
            latest_user_message: The user's latest message text.
            llm_call_chat: An async callable that accepts messages list and returns LLM response.

        Returns:
            A dict with keys:
                - assistant_message (str): The assistant's reply.
                - is_ready_to_generate (bool): Whether enough info has been gathered.
                - summary (dict): Structured summary with known_facts, missing_facts, etc.
        """
        ...

    def _inject_knowledge_context(self, system_prompt: str, knowledge_context: str | None) -> str:
        if not knowledge_context:
            return system_prompt
        rules = _localized_prompt(
            "ai_add_knowledge_context",
            knowledge_context=knowledge_context,
        )
        return f"{system_prompt}\n\n{rules}"

    async def _execute_llm_slot_filling(
        self,
        system_prompt: str,
        current_summary: dict | None,
        latest_user_message: str,
        llm_call_chat: Callable[..., Coroutine[Any, Any, str | None]],
        knowledge_context: str | None = None,
    ) -> dict:
        """
        Generic helper to execute multi-turn LLM slot-filling.
        Handles:
        1. Preserving chat history in summary payload
        2. Calling LLM using full context history
        3. Parsing LLM JSON output to match expected return format
        """
        # 1. Initialize summary
        summary = dict(current_summary or {})
        chat_history = list(summary.get("chat_history", []))
        round_count = int(summary.get("round_count", 0)) + 1

        # 2. Append latest user message
        chat_history.append({"role": "user", "content": latest_user_message})

        # Inject knowledge context
        injected_system_prompt = self._inject_knowledge_context(system_prompt, knowledge_context)

        # 3. Format message history for LLM
        messages = [{"role": "system", "content": injected_system_prompt}] + chat_history

        # 4. Call LLM
        response = await llm_call_chat(
            messages=messages,
            response_format={"type": "json_object"},
        )

        assistant_message = localized_message("ai_add_unavailable")
        is_ready = False
        known_facts = []
        missing_facts = []

        if response:
            try:
                parsed = json.loads(response)
                assistant_message = parsed.get("assistant_message", assistant_message)
                is_ready = bool(parsed.get("is_ready_to_generate", False))
                # Validate and parse known_facts / missing_facts
                known_facts = parsed.get("known_facts", [])
                missing_facts = parsed.get("missing_facts", [])
            except Exception as e:
                logger.exception("Failed to parse LLM interview response")
                # Fallback in case of parse error: use the raw response as message
                assistant_message = response

        # 5. Append assistant reply to history
        chat_history.append({"role": "assistant", "content": assistant_message})

        # 6. Save back to summary
        summary["chat_history"] = chat_history
        summary["round_count"] = round_count
        summary["known_facts"] = known_facts
        summary["missing_facts"] = missing_facts
        summary["target_type"] = self.target_type

        return {
            "assistant_message": assistant_message,
            "is_ready_to_generate": is_ready,
            "summary": summary,
        }


# ---------------------------------------------------------------------------
# Concrete strategies - using real LLM calls and slot-filling
# Class names match the stub skeletons for 100% backward compatibility
# ---------------------------------------------------------------------------

class StubActorInterviewStrategy(BaseInterviewStrategy):
    target_type = "actor"
    required_context = ["actors"]

    async def interview(
        self,
        project_context: dict,
        anchor: dict,
        current_summary: dict | None,
        latest_user_message: str,
        llm_call_chat: Callable[..., Coroutine[Any, Any, str | None]],
        knowledge_context: str | None = None,
    ) -> dict:
        existing_actors = project_context.get("actors", [])
        existing_actors_str = json.dumps(existing_actors, ensure_ascii=False, indent=2)
        system_prompt = _localized_prompt(
            "ai_add_actor_interview",
            existing_actors=existing_actors_str,
        )
        return await self._execute_llm_slot_filling(
            system_prompt=system_prompt,
            current_summary=current_summary,
            latest_user_message=latest_user_message,
            llm_call_chat=llm_call_chat,
            knowledge_context=knowledge_context,
        )


class StubFeatureInterviewStrategy(BaseInterviewStrategy):
    target_type = "feature_leaf"
    required_context = ["features", "actors"]

    async def interview(
        self,
        project_context: dict,
        anchor: dict,
        current_summary: dict | None,
        latest_user_message: str,
        llm_call_chat: Callable[..., Coroutine[Any, Any, str | None]],
        knowledge_context: str | None = None,
    ) -> dict:
        existing_actors = project_context.get("actors", [])
        existing_actors_str = json.dumps(existing_actors, ensure_ascii=False, indent=2)

        existing_features = project_context.get("features", [])
        existing_features_str = json.dumps(existing_features, ensure_ascii=False, indent=2)

        parent_feature_id = anchor.get("parent_feature_id")
        system_prompt = _localized_prompt(
            "ai_add_feature_leaf_interview",
            parent_feature_id=parent_feature_id if parent_feature_id else "null",
            existing_actors=existing_actors_str,
            existing_features=existing_features_str,
        )
        return await self._execute_llm_slot_filling(
            system_prompt=system_prompt,
            current_summary=current_summary,
            latest_user_message=latest_user_message,
            llm_call_chat=llm_call_chat,
            knowledge_context=knowledge_context,
        )


class StubFeatureBranchInterviewStrategy(BaseInterviewStrategy):
    target_type = "feature_branch"
    required_context = ["features", "actors"]

    async def interview(
        self,
        project_context: dict,
        anchor: dict,
        current_summary: dict | None,
        latest_user_message: str,
        llm_call_chat: Callable[..., Coroutine[Any, Any, str | None]],
        knowledge_context: str | None = None,
    ) -> dict:
        existing_features = project_context.get("features", [])
        existing_features_str = json.dumps(existing_features, ensure_ascii=False, indent=2)

        parent_feature_id = anchor.get("parent_feature_id")
        system_prompt = _localized_prompt(
            "ai_add_feature_branch_interview",
            parent_feature_id=parent_feature_id if parent_feature_id else "null",
            existing_features=existing_features_str,
        )
        return await self._execute_llm_slot_filling(
            system_prompt=system_prompt,
            current_summary=current_summary,
            latest_user_message=latest_user_message,
            llm_call_chat=llm_call_chat,
            knowledge_context=knowledge_context,
        )


class StubFlowInterviewStrategy(BaseInterviewStrategy):
    target_type = "flow"
    required_context = ["features", "flows"]

    async def interview(
        self,
        project_context: dict,
        anchor: dict,
        current_summary: dict | None,
        latest_user_message: str,
        llm_call_chat: Callable[..., Coroutine[Any, Any, str | None]],
        knowledge_context: str | None = None,
    ) -> dict:
        existing_flows = project_context.get("flows", [])
        existing_flows_str = json.dumps(existing_flows, ensure_ascii=False, indent=2)

        existing_features = project_context.get("features", [])
        existing_features_str = json.dumps(existing_features, ensure_ascii=False, indent=2)
        system_prompt = _localized_prompt(
            "ai_add_flow_interview",
            existing_flows=existing_flows_str,
            existing_features=existing_features_str,
        )
        return await self._execute_llm_slot_filling(
            system_prompt=system_prompt,
            current_summary=current_summary,
            latest_user_message=latest_user_message,
            llm_call_chat=llm_call_chat,
            knowledge_context=knowledge_context,
        )


class StubBusinessObjectInterviewStrategy(BaseInterviewStrategy):
    target_type = "business_object"
    required_context = ["business_objects", "flows"]

    async def interview(
        self,
        project_context: dict,
        anchor: dict,
        current_summary: dict | None,
        latest_user_message: str,
        llm_call_chat: Callable[..., Coroutine[Any, Any, str | None]],
        knowledge_context: str | None = None,
    ) -> dict:
        existing_bos = project_context.get("business_objects", [])
        existing_bos_str = json.dumps(existing_bos, ensure_ascii=False, indent=2)
        system_prompt = _localized_prompt(
            "ai_add_business_object_interview",
            existing_business_objects=existing_bos_str,
        )
        return await self._execute_llm_slot_filling(
            system_prompt=system_prompt,
            current_summary=current_summary,
            latest_user_message=latest_user_message,
            llm_call_chat=llm_call_chat,
            knowledge_context=knowledge_context,
        )


# ---------------------------------------------------------------------------
# Edit-mode strategies (Phase 2)
# ---------------------------------------------------------------------------

class StubEditActorInterviewStrategy(BaseInterviewStrategy):
    target_type = "edit_actor"
    required_context = ["actors", "features"]

    async def interview(
        self, project_context, anchor, current_summary, latest_user_message, llm_call_chat,
        knowledge_context: str | None = None,
    ) -> dict:
        target_id = anchor.get("target_id")
        original_actor = None
        for a in project_context.get("actors", []):
            if str(a.get("id")) == str(target_id):
                original_actor = a
                break

        original_str = json.dumps(
            original_actor or {"id": target_id},
            ensure_ascii=False,
            indent=2,
        )
        system_prompt = _localized_prompt(
            "ai_add_edit_actor_interview",
            original_object=original_str,
            target_id=target_id,
        )
        return await self._execute_llm_slot_filling(
            system_prompt=system_prompt,
            current_summary=current_summary,
            latest_user_message=latest_user_message,
            llm_call_chat=llm_call_chat,
            knowledge_context=knowledge_context,
        )


class StubEditFeatureInterviewStrategy(BaseInterviewStrategy):
    target_type = "edit_feature"
    required_context = ["features", "actors"]

    async def interview(
        self, project_context, anchor, current_summary, latest_user_message, llm_call_chat,
        knowledge_context: str | None = None,
    ) -> dict:
        target_id = anchor.get("target_id")
        original_feature = None
        for f in project_context.get("features", []):
            if str(f.get("id")) == str(target_id):
                original_feature = f
                break

        original_str = json.dumps(
            original_feature or {"id": target_id},
            ensure_ascii=False,
            indent=2,
        )

        existing_actors = project_context.get("actors", [])
        existing_actors_str = json.dumps(existing_actors, ensure_ascii=False, indent=2)
        system_prompt = _localized_prompt(
            "ai_add_edit_feature_interview",
            original_object=original_str,
            existing_actors=existing_actors_str,
            target_id=target_id,
        )
        return await self._execute_llm_slot_filling(
            system_prompt=system_prompt,
            current_summary=current_summary,
            latest_user_message=latest_user_message,
            llm_call_chat=llm_call_chat,
            knowledge_context=knowledge_context,
        )


class StubEditFlowInterviewStrategy(BaseInterviewStrategy):
    target_type = "edit_flow"
    required_context = ["features", "flows"]

    async def interview(
        self, project_context, anchor, current_summary, latest_user_message, llm_call_chat,
        knowledge_context: str | None = None,
    ) -> dict:
        target_id = anchor.get("target_id")
        original_flow = None
        for f in project_context.get("flows", []):
            if str(f.get("id")) == str(target_id):
                original_flow = f
                break

        original_str = json.dumps(
            original_flow or {"id": target_id},
            ensure_ascii=False,
            indent=2,
        )

        existing_features = project_context.get("features", [])
        existing_features_str = json.dumps(existing_features, ensure_ascii=False, indent=2)
        system_prompt = _localized_prompt(
            "ai_add_edit_flow_interview",
            original_object=original_str,
            existing_features=existing_features_str,
            target_id=target_id,
        )
        return await self._execute_llm_slot_filling(
            system_prompt=system_prompt,
            current_summary=current_summary,
            latest_user_message=latest_user_message,
            llm_call_chat=llm_call_chat,
            knowledge_context=knowledge_context,
        )


class StubEditBusinessObjectInterviewStrategy(BaseInterviewStrategy):
    target_type = "edit_business_object"
    required_context = ["business_objects", "flows"]

    async def interview(
        self, project_context, anchor, current_summary, latest_user_message, llm_call_chat,
        knowledge_context: str | None = None,
    ) -> dict:
        target_id = anchor.get("target_id")
        original_bo = None
        for b in project_context.get("business_objects", []):
            if str(b.get("id")) == str(target_id):
                original_bo = b
                break

        original_str = json.dumps(
            original_bo or {"id": target_id},
            ensure_ascii=False,
            indent=2,
        )
        system_prompt = _localized_prompt(
            "ai_add_edit_business_object_interview",
            original_object=original_str,
            target_id=target_id,
        )
        return await self._execute_llm_slot_filling(
            system_prompt=system_prompt,
            current_summary=current_summary,
            latest_user_message=latest_user_message,
            llm_call_chat=llm_call_chat,
            knowledge_context=knowledge_context,
        )


# ---------------------------------------------------------------------------
# Registry: maps target_type -> strategy instance
# ---------------------------------------------------------------------------

class InterviewStrategyRegistry:
    """Holds all registered interview strategies and dispatches by target_type."""

    def __init__(self):
        self._strategies: dict[str, BaseInterviewStrategy] = {}

    def register(self, strategy: BaseInterviewStrategy) -> None:
        self._strategies[strategy.target_type] = strategy

    def get(self, target_type: str) -> BaseInterviewStrategy:
        strategy = self._strategies.get(target_type)
        if strategy is None:
            raise ValueError(f"unsupported_target_type: {target_type}")
        return strategy

    def has_type(self, target_type: str) -> bool:
        return target_type in self._strategies


def create_default_registry() -> InterviewStrategyRegistry:
    """Create a registry pre-populated with all strategies (add + edit)."""
    registry = InterviewStrategyRegistry()
    # Add-mode strategies
    registry.register(StubActorInterviewStrategy())
    registry.register(StubFeatureInterviewStrategy())
    registry.register(StubFeatureBranchInterviewStrategy())
    registry.register(StubFlowInterviewStrategy())
    registry.register(StubBusinessObjectInterviewStrategy())
    # Edit-mode strategies
    registry.register(StubEditActorInterviewStrategy())
    registry.register(StubEditFeatureInterviewStrategy())
    registry.register(StubEditFlowInterviewStrategy())
    registry.register(StubEditBusinessObjectInterviewStrategy())
    return registry
