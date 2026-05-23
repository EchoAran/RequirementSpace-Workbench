from abc import ABC, abstractmethod

from backend.schemas import NextSuggestion


class StageSuggestionPolicy(ABC):
    @abstractmethod
    async def get_next(
        self,
        project_id: int,
        session,
    ) -> NextSuggestion:
        pass
