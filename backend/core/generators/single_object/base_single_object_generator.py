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


class BaseSingleObjectGenerator(BaseGenerator[SingleObjectGeneratorInput], ABC):
    """Base class for generators that create a single target object.

    Subclasses must implement generate() to return a JSON-decoded dict
    containing exactly one object plus a rationale.
    """

    @abstractmethod
    async def generate(self, input_data: SingleObjectGeneratorInput) -> Any:
        ...
