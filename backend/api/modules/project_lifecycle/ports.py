from abc import ABC, abstractmethod
from backend.api.base_schema import CamelModel

from backend.api.modules.project_lifecycle.schemas.project import ConfirmationStatusEnum


class ActorFeaturePreviewGeneratorPort(ABC):
    """Port defining the boundary for generating actor and feature tree previews.

    Implemented by Local and Skill-backed generators.
    """

    @abstractmethod
    async def generate_actor_and_feature_previews(
        self,
        user_requirements: str,
        user_feedback: str | None,
        knowledge_context: str | None = None,
    ) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
        """Generate draft previews and response previews for actors and features.

        Returns:
            tuple: (actor_previews_for_draft, actor_previews_for_response,
                    feature_previews_for_draft, feature_previews_for_response)
        """
        pass


_project_creation_service = None
_project_service = None


def get_project_creation_service():
    if _project_creation_service is None:
        raise RuntimeError("ProjectCreationService has not been registered! Please call set_project_creation_service() at startup.")
    return _project_creation_service


def set_project_creation_service(service) -> None:
    global _project_creation_service
    _project_creation_service = service


def get_project_service():
    if _project_service is None:
        raise RuntimeError("ProjectService has not been registered! Please call set_project_service() at startup.")
    return _project_service


def set_project_service(service) -> None:
    global _project_service
    _project_service = service

