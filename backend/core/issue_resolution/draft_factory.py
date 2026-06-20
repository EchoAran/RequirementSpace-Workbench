"""Factory for creating resolution drafts (scenario, AC, scope generation).

Extracted from IssueService._create_resolution_draft() to avoid circular
dependency when IssueRepairService needs the same logic.
"""

from backend.api.services.service_registry import (
    acceptance_criteria_generation_service,
    scenario_generation_service,
    scope_generation_service,
)
from backend.schemas import IssueResolution


class IssueResolutionDraftFactory:
    """Creates generation drafts during issue resolution.

    Each method maps a draft_type + payload to the corresponding
    generation service and updates the IssueResolution in-place.
    """

    async def create_draft(
        self,
        project_id: int,
        resolution: IssueResolution,
        session,
    ) -> IssueResolution:
        """Dispatch to the correct draft creator based on action.draft_type."""
        draft_type = resolution.action.get("draft_type")
        payload = resolution.action.get("payload", {})

        if draft_type == "scenario_generation":
            return await self._create_scenario_draft(project_id, resolution, payload, session)
        elif draft_type == "acceptance_criteria_generation":
            return await self._create_ac_draft(project_id, resolution, payload, session)
        elif draft_type == "scope_generation":
            return await self._create_scope_draft(project_id, resolution, payload, session)
        else:
            raise ValueError("unsupported_resolution_draft")

    async def _create_scenario_draft(
        self,
        project_id: int,
        resolution: IssueResolution,
        payload: dict,
        session,
    ) -> IssueResolution:
        feature_id = payload.get("feature_id")
        actor_id = payload.get("actor_id")
        if feature_id is None or actor_id is None:
            raise ValueError("invalid_resolution_payload")

        draft = await scenario_generation_service.create_pair_draft(
            project_id=project_id,
            feature_id=int(feature_id),
            actor_id=int(actor_id),
            session=session,
        )
        return self._attach_draft(resolution, draft)

    async def _create_ac_draft(
        self,
        project_id: int,
        resolution: IssueResolution,
        payload: dict,
        session,
    ) -> IssueResolution:
        scenario_id = payload.get("scenario_id")
        if scenario_id is None:
            raise ValueError("invalid_resolution_payload")

        draft = await acceptance_criteria_generation_service.create_single_draft(
            project_id=project_id,
            scenario_id=int(scenario_id),
            session=session,
        )
        return self._attach_draft(resolution, draft)

    async def _create_scope_draft(
        self,
        project_id: int,
        resolution: IssueResolution,
        payload: dict,
        session,
    ) -> IssueResolution:
        draft = await scope_generation_service.create_draft(
            project_id=project_id,
            session=session,
        )
        return self._attach_draft(resolution, draft)

    @staticmethod
    def _attach_draft(
        resolution: IssueResolution,
        draft: dict,
    ) -> IssueResolution:
        resolution.draftId = draft.get("draft_id")
        resolution.draft = draft
        endpoint = resolution.action.get("endpoint", "")
        resolution.action["endpoint"] = endpoint.format(draft_id=draft.get("draft_id"))
        resolution.action["payload"] = {
            **resolution.action.get("payload", {}),
            "draft_id": draft.get("draft_id"),
        }
        return resolution
