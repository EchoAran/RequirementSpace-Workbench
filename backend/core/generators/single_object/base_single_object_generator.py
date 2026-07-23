"""Base classes for single-object generators in AI-powered conversational addition.

Each generator produces exactly one object (actor, feature, flow, or business_object)
from an interview summary, rather than batch-generating the entire project structure.
"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from backend.core.generators.base_generator import BaseGenerator, GenerateInput
from backend.core.prompt_resolver import resolve_prompt


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
    rules = resolve_prompt("generator_knowledge_context").replace(
        "{{knowledge_context}}",
        knowledge_context,
    )
    return prompt + f"\n\n{rules}"


def serialize_prompt_data(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)
