from abc import ABC, abstractmethod

from backend.schemas import IssueResolution, IssueTarget


class BaseIssueSolver(ABC):
    @abstractmethod
    async def resolve(
        self,
        project_id: int,
        issue_code: str,
        target: IssueTarget | None,
        metadata: dict,
        session,
    ) -> IssueResolution:
        pass
