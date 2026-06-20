from backend.api.services.issue_repair_service import IssueRepairService


class IssueService:
    def __init__(self):
        self._repair_service = IssueRepairService()

    async def resolve_issue(
        self,
        project_id: int,
        issue_id: str | None,
        issue_code: str,
        stage: str | None,
        target: dict | None,
        metadata: dict,
        session,
    ) -> dict:
        """Resolve an issue by delegating to IssueRepairService.

        IssueRepairService handles re-detection, fingerprint/context hash,
        strategy dispatch, and generation draft creation.
        """
        # Load metadata from the request, with issue_id for tracing
        merged_metadata = {**(metadata or {})}
        if issue_id:
            merged_metadata["issue_id"] = issue_id

        return await self._repair_service.resolve(
            project_id=project_id,
            issue_code=issue_code,
            stage=stage,
            target=target,
            metadata=merged_metadata,
            session=session,
        )
