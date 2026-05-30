"""
Interview strategies for AI-powered conversational single-object addition.

Each strategy knows what questions to ask for a specific object type (actor,
feature, flow, business_object), when enough information has been gathered,
and how to produce a structured summary for downstream single-object generators.

Strategies are stateless pure functions: each interview() call receives the
current summary and latest user message, and returns the next assistant reply
plus an updated summary. This design allows session recovery at any point
without replaying full message history.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Coroutine


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


# ---------------------------------------------------------------------------
# Stub strategies — return canned responses, mark ready after 2 rounds
# Used for Phase 1 skeleton verification before real LLM-based strategies
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
    ) -> dict:
        round_count = (current_summary or {}).get("round_count", 0) + 1

        if round_count >= 2:
            return {
                "assistant_message": "好的，我已了解该参与者的信息。可以生成草稿了。",
                "is_ready_to_generate": True,
                "summary": {
                    "target_type": "actor",
                    "known_facts": [
                        {"key": "name", "value": "指定参与者", "source": "stub"},
                        {"key": "description", "value": "由用户描述", "source": "stub"},
                    ],
                    "missing_facts": [],
                    "round_count": round_count,
                },
            }

        return {
            "assistant_message": "请描述该参与者的主要职责或角色边界，例如“普通用户”还是“管理员”？",
            "is_ready_to_generate": False,
            "summary": {
                "target_type": "actor",
                "known_facts": [],
                "missing_facts": ["name", "description"],
                "round_count": round_count,
            },
        }


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
    ) -> dict:
        round_count = (current_summary or {}).get("round_count", 0) + 1

        if round_count >= 3:
            return {
                "assistant_message": "好的，我了解了该功能点的信息。可以生成草稿了。",
                "is_ready_to_generate": True,
                "summary": {
                    "target_type": "feature_leaf",
                    "known_facts": [
                        {"key": "name", "value": "指定功能", "source": "stub"},
                        {"key": "parent_feature", "value": str(anchor.get("parent_feature_id", "未指定")), "source": "anchor"},
                    ],
                    "missing_facts": [],
                    "round_count": round_count,
                },
            }

        return {
            "assistant_message": "请描述这个功能点的主要目标，以及主要由哪个参与者使用？",
            "is_ready_to_generate": False,
            "summary": {
                "target_type": "feature_leaf",
                "known_facts": [],
                "missing_facts": ["name", "actor", "description"],
                "round_count": round_count,
            },
        }


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
    ) -> dict:
        round_count = (current_summary or {}).get("round_count", 0) + 1

        if round_count >= 2:
            return {
                "assistant_message": "好的，我了解了该功能模块的信息。可以生成草稿了。",
                "is_ready_to_generate": True,
                "summary": {
                    "target_type": "feature_branch",
                    "known_facts": [
                        {"key": "name", "value": "指定功能模块", "source": "stub"},
                    ],
                    "missing_facts": [],
                    "round_count": round_count,
                },
            }

        return {
            "assistant_message": "请描述这个功能模块的定位，例如是“用户管理”还是“数据报表”大类？",
            "is_ready_to_generate": False,
            "summary": {
                "target_type": "feature_branch",
                "known_facts": [],
                "missing_facts": ["name", "description"],
                "round_count": round_count,
            },
        }


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
    ) -> dict:
        round_count = (current_summary or {}).get("round_count", 0) + 1

        if round_count >= 2:
            return {
                "assistant_message": "好的，我了解了该流程的信息。可以生成草稿了。",
                "is_ready_to_generate": True,
                "summary": {
                    "target_type": "flow",
                    "known_facts": [
                        {"key": "name", "value": "指定流程", "source": "stub"},
                    ],
                    "missing_facts": [],
                    "round_count": round_count,
                },
            }

        return {
            "assistant_message": "请描述这个流程覆盖哪些功能，以及它的触发条件是什么？",
            "is_ready_to_generate": False,
            "summary": {
                "target_type": "flow",
                "known_facts": [],
                "missing_facts": ["name", "feature_ids", "trigger"],
                "round_count": round_count,
            },
        }


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
    ) -> dict:
        round_count = (current_summary or {}).get("round_count", 0) + 1

        if round_count >= 2:
            return {
                "assistant_message": "好的，我了解了该业务数据对象的信息。可以生成草稿了。",
                "is_ready_to_generate": True,
                "summary": {
                    "target_type": "business_object",
                    "known_facts": [
                        {"key": "name", "value": "指定业务对象", "source": "stub"},
                    ],
                    "missing_facts": [],
                    "round_count": round_count,
                },
            }

        return {
            "assistant_message": "请描述这个业务数据对象的名称和主要用途，例如“订单”包含哪些关键信息？",
            "is_ready_to_generate": False,
            "summary": {
                "target_type": "business_object",
                "known_facts": [],
                "missing_facts": ["name", "description"],
                "round_count": round_count,
            },
        }


# ---------------------------------------------------------------------------
# Edit-mode stub interview strategies (Phase 2)
# These follow the same contract as add-mode strategies but target edit_*
# sessions. The conversation summary feeds into EditGenerator as user message.
# ---------------------------------------------------------------------------

class StubEditActorInterviewStrategy(BaseInterviewStrategy):
    target_type = "edit_actor"
    required_context = ["actors", "features"]

    async def interview(
        self, project_context, anchor, current_summary, latest_user_message, llm_call_chat,
    ) -> dict:
        round_count = (current_summary or {}).get("round_count", 0) + 1
        if round_count >= 2:
            return {
                "assistant_message": "好的，已了解修改内容。可以生成编辑草稿了。",
                "is_ready_to_generate": True,
                "summary": {
                    "target_type": "edit_actor",
                    "known_facts": [
                        {"key": "edit_target", "value": f"actor:{anchor.get('target_id', '?')}", "source": "anchor"},
                        {"key": "desired_change", "value": latest_user_message, "source": "user_said"},
                    ],
                    "missing_facts": [],
                    "round_count": round_count,
                },
            }
        return {
            "assistant_message": "请描述你想对这个参与者做什么修改？比如修改名称、描述。",
            "is_ready_to_generate": False,
            "summary": {
                "target_type": "edit_actor",
                "known_facts": [],
                "missing_facts": ["desired_change"],
                "round_count": round_count,
            },
        }


class StubEditFeatureInterviewStrategy(BaseInterviewStrategy):
    target_type = "edit_feature"
    required_context = ["features", "actors"]

    async def interview(
        self, project_context, anchor, current_summary, latest_user_message, llm_call_chat,
    ) -> dict:
        round_count = (current_summary or {}).get("round_count", 0) + 1
        if round_count >= 2:
            return {
                "assistant_message": "好的，已了解修改内容。可以生成编辑草稿了。",
                "is_ready_to_generate": True,
                "summary": {
                    "target_type": "edit_feature",
                    "known_facts": [
                        {"key": "edit_target", "value": f"feature:{anchor.get('target_id', '?')}", "source": "anchor"},
                        {"key": "desired_change", "value": latest_user_message, "source": "user_said"},
                    ],
                    "missing_facts": [],
                    "round_count": round_count,
                },
            }
        return {
            "assistant_message": "请描述你想对这个功能做什么修改？比如修改名称、描述或关联参与者。",
            "is_ready_to_generate": False,
            "summary": {
                "target_type": "edit_feature",
                "known_facts": [],
                "missing_facts": ["desired_change"],
                "round_count": round_count,
            },
        }


class StubEditFlowInterviewStrategy(BaseInterviewStrategy):
    target_type = "edit_flow"
    required_context = ["features", "flows"]

    async def interview(
        self, project_context, anchor, current_summary, latest_user_message, llm_call_chat,
    ) -> dict:
        round_count = (current_summary or {}).get("round_count", 0) + 1
        if round_count >= 2:
            return {
                "assistant_message": "好的，已了解修改内容。可以生成编辑草稿了。",
                "is_ready_to_generate": True,
                "summary": {
                    "target_type": "edit_flow",
                    "known_facts": [
                        {"key": "edit_target", "value": f"flow:{anchor.get('target_id', '?')}", "source": "anchor"},
                        {"key": "desired_change", "value": latest_user_message, "source": "user_said"},
                    ],
                    "missing_facts": [],
                    "round_count": round_count,
                },
            }
        return {
            "assistant_message": "请描述你想对这个流程做什么修改？比如修改名称、描述或关联功能。",
            "is_ready_to_generate": False,
            "summary": {
                "target_type": "edit_flow",
                "known_facts": [],
                "missing_facts": ["desired_change"],
                "round_count": round_count,
            },
        }


class StubEditBusinessObjectInterviewStrategy(BaseInterviewStrategy):
    target_type = "edit_business_object"
    required_context = ["business_objects", "flows"]

    async def interview(
        self, project_context, anchor, current_summary, latest_user_message, llm_call_chat,
    ) -> dict:
        round_count = (current_summary or {}).get("round_count", 0) + 1
        if round_count >= 2:
            return {
                "assistant_message": "好的，已了解修改内容。可以生成编辑草稿了。",
                "is_ready_to_generate": True,
                "summary": {
                    "target_type": "edit_business_object",
                    "known_facts": [
                        {"key": "edit_target", "value": f"business_object:{anchor.get('target_id', '?')}", "source": "anchor"},
                        {"key": "desired_change", "value": latest_user_message, "source": "user_said"},
                    ],
                    "missing_facts": [],
                    "round_count": round_count,
                },
            }
        return {
            "assistant_message": "请描述你想对这个业务数据对象做什么修改？比如修改名称或描述。",
            "is_ready_to_generate": False,
            "summary": {
                "target_type": "edit_business_object",
                "known_facts": [],
                "missing_facts": ["desired_change"],
                "round_count": round_count,
            },
        }


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
    """Create a registry pre-populated with all stub strategies (add + edit)."""
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
