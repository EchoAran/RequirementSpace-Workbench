from backend.api.modules.diagnosis_quality.perception.application.draft_creator import (
    PerceptionDraftCreator,
)
from backend.api.modules.diagnosis_quality.perception.application.draft_discarder import (
    PerceptionDraftDiscarder,
)
from backend.api.modules.diagnosis_quality.perception.application.draft_confirmer import (
    PerceptionDraftConfirmer,
)


class PerceptionSlotFillingService:
    def __init__(self):
        self._creator = PerceptionDraftCreator()
        self._discarder = PerceptionDraftDiscarder()
        self._confirmer = PerceptionDraftConfirmer()

        # Retain filler attributes for compatibility
        self._actors_filler = self._creator._actors_filler
        self._features_filler = self._creator._features_filler
        self._scenarios_filler = self._creator._scenarios_filler
        self._acceptance_criteria_filler = self._creator._acceptance_criteria_filler
        self._flows_filler = self._creator._flows_filler

    async def create_actor_draft(
        self,
        project_id: int,
        owner_user_id: int,
        perception_job_id: int,
        session,
    ) -> dict:
        return await self._creator.create_actor_draft(
            project_id=project_id,
            owner_user_id=owner_user_id,
            perception_job_id=perception_job_id,
            session=session,
        )

    async def create_feature_draft(
        self,
        project_id: int,
        owner_user_id: int,
        perception_job_id: int,
        session,
    ) -> dict:
        return await self._creator.create_feature_draft(
            project_id=project_id,
            owner_user_id=owner_user_id,
            perception_job_id=perception_job_id,
            session=session,
        )

    async def create_scenario_draft(
        self,
        project_id: int,
        owner_user_id: int,
        perception_job_id: int,
        session,
    ) -> dict:
        return await self._creator.create_scenario_draft(
            project_id=project_id,
            owner_user_id=owner_user_id,
            perception_job_id=perception_job_id,
            session=session,
        )

    async def create_acceptance_criteria_draft(
        self,
        project_id: int,
        owner_user_id: int,
        perception_job_id: int,
        session,
    ) -> dict:
        return await self._creator.create_acceptance_criteria_draft(
            project_id=project_id,
            owner_user_id=owner_user_id,
            perception_job_id=perception_job_id,
            session=session,
        )

    async def create_flow_draft(
        self,
        project_id: int,
        owner_user_id: int,
        perception_job_id: int,
        session,
    ) -> dict:
        return await self._creator.create_flow_draft(
            project_id=project_id,
            owner_user_id=owner_user_id,
            perception_job_id=perception_job_id,
            session=session,
        )

    async def regenerate_draft(
        self,
        draft_id: str,
        owner_user_id: int,
        session,
        user_feedback: str | None = None,
    ) -> dict:
        return await self._creator.regenerate_draft(
            draft_id=draft_id,
            owner_user_id=owner_user_id,
            session=session,
            user_feedback=user_feedback,
        )

    async def confirm_draft(
        self,
        draft_id: str,
        owner_user_id: int,
        session,
    ) -> dict:
        return await self._confirmer.confirm_draft(
            draft_id=draft_id,
            owner_user_id=owner_user_id,
            session=session,
        )

    async def discard_draft(
        self,
        draft_id: str,
        owner_user_id: int,
    ) -> dict:
        return await self._discarder.discard_draft(
            draft_id=draft_id,
            owner_user_id=owner_user_id,
        )
