"""Base classes for edit-mode generators in AI-powered conversational editing.

Each edit generator produces a diff describing changes to an existing object,
rather than a full object definition like add-mode generators.
"""

from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from typing import Any

from backend.core.generators.base_generator import BaseGenerator, GenerateInput


@dataclass
class EditGeneratorInput(GenerateInput):
    """Input for all edit-mode generators.

    Attributes:
        user_requirements: The project's full requirements text.
        project_context: Pre-loaded project data (actors, features, etc.).
        conversation_summary: The summary_payload from the edit interview session.
        target_type: The original object type (actor, feature, flow, business_object).
        original_object: The current state of the object being edited.
        editable_fields: List of field names allowed to be edited.
    """
    user_requirements: str
    project_context: dict
    conversation_summary: dict
    target_type: str = ""
    original_object: dict = field(default_factory=dict)
    editable_fields: list[str] = field(default_factory=list)


class BaseEditGenerator(BaseGenerator[EditGeneratorInput], ABC):
    """Base class for generators that produce edit diffs.

    Subclasses must set target_object_type and editable_fields.
    The generate() method follows a template: assemble prompt → call LLM →
    validate diff fields → return diff.
    """

    target_object_type: str = ""
    editable_fields: list[str] = []

    @abstractmethod
    async def generate(self, input_data: EditGeneratorInput) -> Any:
        ...
