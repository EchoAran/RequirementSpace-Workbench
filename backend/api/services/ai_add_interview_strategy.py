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

logger = logging.getLogger(__name__)


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

    async def _execute_llm_slot_filling(
        self,
        system_prompt: str,
        current_summary: dict | None,
        latest_user_message: str,
        llm_call_chat: Callable[..., Coroutine[Any, Any, str | None]],
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

        # 3. Format message history for LLM
        messages = [{"role": "system", "content": system_prompt}] + chat_history

        # 4. Call LLM
        response = await llm_call_chat(
            messages=messages,
            response_format={"type": "json_object"},
        )

        assistant_message = "抱歉，系统暂时无法处理您的请求，请稍候再试。"
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
    ) -> dict:
        existing_actors = project_context.get("actors", [])
        existing_actors_str = "\n".join(
            f"- {a.get('name')}: {a.get('description')}" for a in existing_actors
        ) if existing_actors else "（无已有的参与者）"

        system_prompt = f"""你是一个专业的软件需求工程专家，正在通过对话访谈收集“参与者（Actor，即系统中的用户角色或外部系统）”的信息。
你的目标是收集并填满以下槽位（Slots）：
1. name (参与者名称，例如：普通用户、系统管理员、仓库盘点员。必须简短明确，不能重名)。
2. description (参与者职责、权限和角色边界的详细描述)。

当前项目的已有参与者列表如下：
{existing_actors_str}

访谈行为准则：
- 仔细阅读历史对话，提取已提供的信息。
- 如果信息不全，请友好地追问缺失的槽位（例如询问职责细节或建议更规范的名称），每次只问一到两个清晰的问题，保持语气专业体贴。
- 如果已经收集到了足够清晰的参与者名称和描述，请设置 is_ready_to_generate 为 true，并在 assistant_message 中友好地通知用户。
- 确保参与者名称与项目已有的参与者不重复。如果重复，请委婉地提示用户修改。

你必须严格以 JSON 格式返回，不要包含任何 markdown 包装，格式必须是：
{{
  "assistant_message": "你的自然语言回复，用于和用户交谈、提问或确认",
  "is_ready_to_generate": true/false (是否已集齐所有关键信息),
  "known_facts": [
    {{"key": "name", "value": "提取到的参与者名称"}},
    {{"key": "description", "value": "提取到的职责描述"}}
  ],
  "missing_facts": ["未收集到的字段列表，如 name 或 description"]
}}
"""
        return await self._execute_llm_slot_filling(
            system_prompt=system_prompt,
            current_summary=current_summary,
            latest_user_message=latest_user_message,
            llm_call_chat=llm_call_chat,
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
    ) -> dict:
        existing_actors = project_context.get("actors", [])
        existing_actors_str = "\n".join(
            f"- ID={a.get('id')}: {a.get('name')}" for a in existing_actors
        ) if existing_actors else "（无已有的参与者）"

        existing_features = project_context.get("features", [])
        existing_features_str = "\n".join(
            f"- ID={f.get('id')}: {f.get('name')} (parent_id={f.get('parent_id')})" for f in existing_features
        ) if existing_features else "（无已有的功能点）"

        parent_feature_id = anchor.get("parent_feature_id")
        parent_str = f"ID={parent_feature_id}" if parent_feature_id else "无父级功能点（属于根节点）"

        system_prompt = f"""你是一个专业的软件需求工程专家，正在通过对话收集“功能点（Feature Leaf，即最底层的叶子节点功能点）”的信息。
你的目标是收集并填满以下槽位（Slots）：
1. name (功能点名称，例如：导出销售报表、重置用户密码。必须简短且表达清晰)。
2. description (该功能点的主要目标、业务逻辑和使用场景)。
3. actor_ids (可以使用/触发此功能的参与者 ID 列表。必须从已有参与者中选择，可以关联多个，例如 [1, 2])。

该新功能关联的父级功能：{parent_str}

当前项目的已有参与者：
{existing_actors_str}

当前项目的已有功能点列表：
{existing_features_str}

访谈行为准则：
- 仔细阅读历史对话，提取已提供的信息。
- 引导用户指定合适的参与者。如果用户描述了参与者名称，请在 `known_facts` 中映射到相应的参与者 ID；如果描述的角色在已有参与者中不存在，请提示用户或询问。
- 如果已经收集到了足够清晰的功能名称、描述以及关联的参与者，请设置 is_ready_to_generate 为 true，并在 assistant_message 中告知用户。
- 确保功能名称在同一个父级下不重复。

你必须严格以 JSON 格式返回，格式如下：
{{
  "assistant_message": "你的回复内容",
  "is_ready_to_generate": true/false,
  "known_facts": [
    {{"key": "name", "value": "提取到的功能点名称"}},
    {{"key": "description", "value": "提取到的功能点描述"}},
    {{"key": "actor_ids", "value": [1, 2]}},
    {{"key": "parent_id", "value": {parent_feature_id if parent_feature_id else "null"}}},
    {{"key": "feature_kind", "value": "leaf"}}
  ],
  "missing_facts": ["未收集到的字段列表"]
}}
"""
        return await self._execute_llm_slot_filling(
            system_prompt=system_prompt,
            current_summary=current_summary,
            latest_user_message=latest_user_message,
            llm_call_chat=llm_call_chat,
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
    ) -> dict:
        existing_features = project_context.get("features", [])
        existing_features_str = "\n".join(
            f"- ID={f.get('id')}: {f.get('name')} (parent_id={f.get('parent_id')})" for f in existing_features
        ) if existing_features else "（无已有的功能点）"

        parent_feature_id = anchor.get("parent_feature_id")
        parent_str = f"ID={parent_feature_id}" if parent_feature_id else "无父级功能点（属于根节点）"

        system_prompt = f"""你是一个专业的软件需求工程专家，正在通过对话收集“功能模块（Feature Branch，即包含子功能的父节点）”的信息。
你的目标是收集并填满以下槽位（Slots）：
1. name (功能模块名称，例如：用户管理模块、财务报表模块。必须简短且表达清晰)。
2. description (该功能模块的业务定位、包含的预期功能范围说明)。

该新功能模块关联的父级功能：{parent_str}

当前项目的已有功能树结构列表：
{existing_features_str}

访谈行为准则：
- 仔细阅读历史对话，提取已提供的信息。
- 如果已经收集到了足够清晰的功能模块名称和描述，请设置 is_ready_to_generate 为 true，并在 assistant_message 中告知用户。
- 确保功能模块名称在同一个父级下不重复。

你必须严格以 JSON 格式返回，格式如下：
{{
  "assistant_message": "你的回复内容",
  "is_ready_to_generate": true/false,
  "known_facts": [
    {{"key": "name", "value": "提取到的功能模块名称"}},
    {{"key": "description", "value": "提取到的功能模块描述"}},
    {{"key": "parent_id", "value": {parent_feature_id if parent_feature_id else "null"}}},
    {{"key": "feature_kind", "value": "branch"}}
  ],
  "missing_facts": ["未收集到的字段列表"]
}}
"""
        return await self._execute_llm_slot_filling(
            system_prompt=system_prompt,
            current_summary=current_summary,
            latest_user_message=latest_user_message,
            llm_call_chat=llm_call_chat,
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
    ) -> dict:
        existing_flows = project_context.get("flows", [])
        existing_flows_str = "\n".join(
            f"- {f.get('name')}" for f in existing_flows
        ) if existing_flows else "（无已有的流程）"

        existing_features = project_context.get("features", [])
        existing_features_str = "\n".join(
            f"- ID={f.get('id')}: {f.get('name')}" for f in existing_features
        ) if existing_features else "（无已有的功能点）"

        system_prompt = f"""你是一个专业的软件需求工程专家，正在通过对话收集“业务流程（Flow）”的信息。
你的目标是收集以下槽位（Slots）：
1. name (业务流程名称，例如：用户下单支付流程、管理员审核文章流程。必须简短且表达清晰)。
2. description (该业务流程的描述，即其触发条件、主要步骤和期望的结果)。
3. feature_ids (该业务流程覆盖或关联的功能点 ID 列表。必须从已有功能点中选择，通常为叶子节点，可以关联多个，例如 [1, 2])。

当前项目的已有流程：
{existing_flows_str}

当前项目的已有功能点列表（只有功能点可以被关联到流程中，请引导用户从这些已有功能中选择）：
{existing_features_str}

访谈行为准则：
- 仔细阅读历史对话，提取已提供的信息。
- 引导用户指定该流程覆盖的功能点。如果用户提到了功能点名称，请通过语义匹配到已有功能的 ID。
- 如果已经收集到了足够清晰的业务流程名称、描述以及关联的功能点，请设置 is_ready_to_generate 为 true，并在 assistant_message 中告知用户。
- 确保业务流程名称不与已有流程冲突。

你必须严格以 JSON 格式返回，格式如下：
{{
  "assistant_message": "你的回复内容",
  "is_ready_to_generate": true/false,
  "known_facts": [
    {{"key": "name", "value": "提取到的业务流程名称"}},
    {{"key": "description", "value": "提取到的业务流程描述"}},
    {{"key": "feature_ids", "value": [1, 2]}}
  ],
  "missing_facts": ["未收集到的字段列表"]
}}
"""
        return await self._execute_llm_slot_filling(
            system_prompt=system_prompt,
            current_summary=current_summary,
            latest_user_message=latest_user_message,
            llm_call_chat=llm_call_chat,
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
    ) -> dict:
        existing_bos = project_context.get("business_objects", [])
        existing_bos_str = "\n".join(
            f"- {b.get('name')}" for b in existing_bos
        ) if existing_bos else "（无已有的业务数据对象）"

        system_prompt = f"""你是一个专业的软件需求工程专家，正在通过对话收集“业务数据对象（Business Object，如“订单”、“商品”等数据模型）”的信息。
你的目标是收集以下槽位（Slots）：
1. name (数据对象名称，例如：订单、用户信息、商品。必须简短且不能与已有重名)。
2. description (该业务对象的用途和定义描述)。
3. attributes (该数据对象包含的关键属性列表。每个属性需要包含 name（属性名）、description（属性描述）、data_type（数据类型，如 string, int, boolean 等）和 example（示例值）)。

当前项目的已有业务对象：
{existing_bos_str}

访谈行为准则：
- 引导用户确定该对象的名称、描述和关键属性。
- 如果用户说了部分属性，请引导他们确认这些属性，或主动推荐一些合理的相关属性（如：创建时间、状态等）供用户选择。
- 当收集到明确的名称、描述以及至少两个以上的关键属性（且用户觉得足够了）时，请设置 is_ready_to_generate 为 true，并在 assistant_message 中告知用户。
- 确保名称不与已有对象冲突。

你必须严格以 JSON 格式返回，格式如下：
{{
  "assistant_message": "你的回复内容",
  "is_ready_to_generate": true/false,
  "known_facts": [
    {{"key": "name", "value": "提取到的数据对象名称"}},
    {{"key": "description", "value": "提取到的数据对象描述"}},
    {{"key": "attributes", "value": [{{"name": "id", "description": "唯一标识", "data_type": "int", "example": "123"}}]}}
  ],
  "missing_facts": ["未收集到的字段列表"]
}}
"""
        return await self._execute_llm_slot_filling(
            system_prompt=system_prompt,
            current_summary=current_summary,
            latest_user_message=latest_user_message,
            llm_call_chat=llm_call_chat,
        )


# ---------------------------------------------------------------------------
# Edit-mode strategies (Phase 2)
# ---------------------------------------------------------------------------

class StubEditActorInterviewStrategy(BaseInterviewStrategy):
    target_type = "edit_actor"
    required_context = ["actors", "features"]

    async def interview(
        self, project_context, anchor, current_summary, latest_user_message, llm_call_chat,
    ) -> dict:
        target_id = anchor.get("target_id")
        original_actor = None
        for a in project_context.get("actors", []):
            if str(a.get("id")) == str(target_id):
                original_actor = a
                break

        original_str = f"名称: {original_actor.get('name')}\n描述: {original_actor.get('description')}" if original_actor else f"ID={target_id} (未找到原信息)"

        system_prompt = f"""你是一个专业的软件需求工程专家，正在通过对话协助用户修改一个已有的“参与者（Actor）”对象。

要修改的原始对象信息如下：
{original_str}

你的目标是收集并整理用户对该对象的所有修改诉求（Desired Changes）。
你可以和用户进行自然的多轮对话，澄清修改细节（例如：修改名称、描述或关联项）。

访谈行为准则：
- 仔细阅读历史对话，提取已提供的信息。
- 确认用户所有想要修改的内容，向用户进行确认。
- 当用户表达完所有修改意愿并且确认修改方案时，请设置 is_ready_to_generate 为 true，并在 assistant_message 中告知用户已准备好生成编辑草稿。
- 核心要求：在 `known_facts` 的 `desired_change` 字段中，提供一个非常详尽、全面、格式优美的 Markdown 文本，总结用户要求的所有具体修改意图。

你必须严格以 JSON 格式返回，格式如下：
{{
  "assistant_message": "你的回复内容",
  "is_ready_to_generate": true/false,
  "known_facts": [
    {{"key": "edit_target", "value": "actor:{target_id}"}},
    {{"key": "desired_change", "value": "对本次修改意图的完整、详尽、格式优美的 Markdown 总结"}}
  ],
  "missing_facts": ["未收集到的修改细节字段列表"]
}}
"""
        return await self._execute_llm_slot_filling(
            system_prompt=system_prompt,
            current_summary=current_summary,
            latest_user_message=latest_user_message,
            llm_call_chat=llm_call_chat,
        )


class StubEditFeatureInterviewStrategy(BaseInterviewStrategy):
    target_type = "edit_feature"
    required_context = ["features", "actors"]

    async def interview(
        self, project_context, anchor, current_summary, latest_user_message, llm_call_chat,
    ) -> dict:
        target_id = anchor.get("target_id")
        original_feature = None
        for f in project_context.get("features", []):
            if str(f.get("id")) == str(target_id):
                original_feature = f
                break

        original_str = f"名称: {original_feature.get('name')}\n父节点ID: {original_feature.get('parent_id') if original_feature else 'null'}" if original_feature else f"ID={target_id} (未找到原信息)"

        existing_actors = project_context.get("actors", [])
        existing_actors_str = "\n".join(
            f"- ID={a.get('id')}: {a.get('name')}" for a in existing_actors
        ) if existing_actors else "（无已有的参与者）"

        system_prompt = f"""你是一个专业的软件需求工程专家，正在通过对话协助用户修改一个已有的“功能点/功能模块（Feature）”对象。

要修改的原始对象信息如下：
{original_str}

当前项目关联的参与者：
{existing_actors_str}

你的目标是收集并整理用户对该对象的所有修改诉求（Desired Changes）。
你可以和用户进行自然的多轮对话，澄清修改细节（例如：修改名称、描述或修改关联的参与者等）。

访谈行为准则：
- 仔细阅读历史对话，提取已提供的信息。
- 确认用户所有想要修改的内容。如果涉及修改关联的参与者，请引导并映射至已有参与者 ID。
- 当用户表达完所有修改意愿并且确认修改方案时，请设置 is_ready_to_generate 为 true，并在 assistant_message 中告知用户已准备好生成编辑草稿。
- 核心要求：在 `known_facts` 的 `desired_change` 字段中，提供一个非常详尽、全面、格式优美的 Markdown 文本，总结用户要求的所有具体修改意图。

你必须严格以 JSON 格式返回，格式如下：
{{
  "assistant_message": "你的回复内容",
  "is_ready_to_generate": true/false,
  "known_facts": [
    {{"key": "edit_target", "value": "feature:{target_id}"}},
    {{"key": "desired_change", "value": "对本次修改意图的完整、详尽、格式优美的 Markdown 总结，包括要添加或移除的参与者 ID/名称"}}
  ],
  "missing_facts": ["未收集到的修改细节字段列表"]
}}
"""
        return await self._execute_llm_slot_filling(
            system_prompt=system_prompt,
            current_summary=current_summary,
            latest_user_message=latest_user_message,
            llm_call_chat=llm_call_chat,
        )


class StubEditFlowInterviewStrategy(BaseInterviewStrategy):
    target_type = "edit_flow"
    required_context = ["features", "flows"]

    async def interview(
        self, project_context, anchor, current_summary, latest_user_message, llm_call_chat,
    ) -> dict:
        target_id = anchor.get("target_id")
        original_flow = None
        for f in project_context.get("flows", []):
            if str(f.get("id")) == str(target_id):
                original_flow = f
                break

        original_str = f"名称: {original_flow.get('name')}" if original_flow else f"ID={target_id} (未找到原信息)"

        existing_features = project_context.get("features", [])
        existing_features_str = "\n".join(
            f"- ID={f.get('id')}: {f.get('name')}" for f in existing_features
        ) if existing_features else "（无已有的功能点）"

        system_prompt = f"""你是一个专业的软件需求工程专家，正在通过对话协助用户修改一个已有的“业务流程（Flow）”对象。

要修改的原始对象信息如下：
{original_str}

当前项目的已有功能点列表：
{existing_features_str}

你的目标是收集并整理用户对该对象的所有修改诉求（Desired Changes）。
你可以和用户进行自然的多轮对话，澄清修改细节（例如：修改名称、描述或修改流程关联的功能点等）。

访谈行为准则：
- 仔细阅读历史对话，提取已提供的信息。
- 确认用户所有想要修改的内容。如果涉及修改关联的功能点，请映射至已有功能点 ID。
- 当用户表达完所有修改意愿并且确认修改方案时，请设置 is_ready_to_generate 为 true，并在 assistant_message 中告知用户已准备好生成编辑草稿。
- 核心要求：在 `known_facts` 的 `desired_change` 字段中，提供一个非常详尽、全面、格式优美的 Markdown 文本，总结用户要求的所有具体修改意图。

你必须严格以 JSON 格式返回，格式如下：
{{
  "assistant_message": "你的回复内容",
  "is_ready_to_generate": true/false,
  "known_facts": [
    {{"key": "edit_target", "value": "flow:{target_id}"}},
    {{"key": "desired_change", "value": "对本次修改意图的完整、详尽、格式优美的 Markdown 总结"}}
  ],
  "missing_facts": ["未收集到的修改细节字段列表"]
}}
"""
        return await self._execute_llm_slot_filling(
            system_prompt=system_prompt,
            current_summary=current_summary,
            latest_user_message=latest_user_message,
            llm_call_chat=llm_call_chat,
        )


class StubEditBusinessObjectInterviewStrategy(BaseInterviewStrategy):
    target_type = "edit_business_object"
    required_context = ["business_objects", "flows"]

    async def interview(
        self, project_context, anchor, current_summary, latest_user_message, llm_call_chat,
    ) -> dict:
        target_id = anchor.get("target_id")
        original_bo = None
        for b in project_context.get("business_objects", []):
            if str(b.get("id")) == str(target_id):
                original_bo = b
                break

        original_str = f"名称: {original_bo.get('name')}" if original_bo else f"ID={target_id} (未找到原信息)"

        system_prompt = f"""你是一个专业的软件需求工程专家，正在通过对话协助用户修改一个已有的“业务数据对象（Business Object）”对象。

要修改的原始对象信息如下：
{original_str}

你的目标是收集并整理用户对该对象的所有修改诉求（Desired Changes）。
你可以和用户进行自然的多轮对话，澄清修改细节（例如：修改名称、描述或添加/修改属性字段）。

访谈行为准则：
- 仔细阅读历史对话，提取已提供的信息。
- 确认用户所有想要修改的内容。如果涉及添加或修改字段属性，请收集属性名、描述、类型和示例值。
- 当用户表达完所有修改意愿并且确认修改方案时，请设置 is_ready_to_generate 为 true，并在 assistant_message 中告知用户已准备好生成编辑草稿。
- 核心要求：在 `known_facts` 的 `desired_change` 字段中，提供一个非常详尽、全面、格式优美的 Markdown 文本，总结用户要求的所有具体修改意图。

你必须严格以 JSON 格式返回，格式如下：
{{
  "assistant_message": "你的回复内容",
  "is_ready_to_generate": true/false,
  "known_facts": [
    {{"key": "edit_target", "value": "business_object:{target_id}"}},
    {{"key": "desired_change", "value": "对本次修改意图的完整、详尽、格式优美的 Markdown 总结"}}
  ],
  "missing_facts": ["未收集到的修改细节字段列表"]
}}
"""
        return await self._execute_llm_slot_filling(
            system_prompt=system_prompt,
            current_summary=current_summary,
            latest_user_message=latest_user_message,
            llm_call_chat=llm_call_chat,
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
