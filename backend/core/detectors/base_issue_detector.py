from abc import ABC, abstractmethod

from backend.schemas import Issue


class BaseIssueDetector(ABC):
    @abstractmethod
    async def detect(self, project_id: int, session) -> list[Issue]:
        pass
