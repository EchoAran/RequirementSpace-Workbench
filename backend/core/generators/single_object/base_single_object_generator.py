"""Base classes for single-object generators in AI-powered conversational addition.

Each generator produces exactly one object (actor, feature, flow, or business_object)
from an interview summary, rather than batch-generating the entire project structure.
"""

from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import Any

from backend.core.generators.base_generator import BaseGenerator, GenerateInput


@dataclass
class SingleObjectGeneratorInput(GenerateInput):
    """Unified input for all single-object generators.

    Attributes:
        user_requirements: The project's full requirements text.
        project_context: Pre-loaded project data (actors, features, etc.).
        conversation_summary: The summary_payload from the interview session.
    """
    user_requirements: str
    project_context: dict
    conversation_summary: dict
    knowledge_context: str | None = None


class BaseSingleObjectGenerator(BaseGenerator[SingleObjectGeneratorInput], ABC):
    """Base class for generators that create a single target object.

    Subclasses must implement generate() to return a JSON-decoded dict
    containing exactly one object plus a rationale.
    """

    @abstractmethod
    async def generate(self, input_data: SingleObjectGeneratorInput) -> Any:
        ...


def inject_generator_knowledge_context(prompt: str, knowledge_context: str | None) -> str:
    if not knowledge_context:
        return prompt

    rules = f"""
# 知识库参考信息与规则
{knowledge_context}

规则：
1. 知识库内容用于补充业务事实和约束。
2. 用户在当前对话中确认的内容和意图（输入）绝对优先于知识库中的参考内容。
3. 如果发现知识库中已存在相同或类似的候选对象/重复需求，应以合理的方式合并或在生成时予以考虑，但只能生成当前这一个目标对象，不要批量生成多个对象。
"""
    if "# 输出格式说明" in prompt:
        return prompt.replace("# 输出格式说明", f"{rules}\n\n# 输出格式说明")
    return prompt + f"\n\n{rules}"

