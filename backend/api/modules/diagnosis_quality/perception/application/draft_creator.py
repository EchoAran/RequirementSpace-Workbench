from uuid import uuid4

from backend.core.perceptrons.slot_fillers.acceptance_criteria_filler import (
    AcceptanceCriteriaFiller,
)
from backend.core.perceptrons.slot_fillers.actors_filler import (
    ActorsFiller,
)
from backend.core.perceptrons.slot_fillers.features_filler import (
    FeaturesFiller,
)
from backend.core.perceptrons.slot_fillers.flows_filler import (
    FlowsFiller,
)
from backend.core.perceptrons.slot_fillers.scenarios_filler import (
    ScenariosFiller,
)
from backend.api.modules.diagnosis_quality.perception.application.preview_builders import (
    PerceptionPreviewBuilder,
)


class PerceptionDraftCreator:
    def __init__(self):
        # State wrappers for filling slots, kept as private attributes for compatibility
        self._actors_filler = ActorsFiller()
        self._features_filler = FeaturesFiller()
        self._scenarios_filler = ScenariosFiller()
        self._acceptance_criteria_filler = AcceptanceCriteriaFiller()
        self._flows_filler = FlowsFiller()

    async def create_actor_draft(
        self,
        project_id: int,
        owner_user_id: int,
        perception_job_id: int,
        session,
    ) -> dict:
        return await self._create_draft(
            project_id=project_id,
            owner_user_id=owner_user_id,
            perception_job_id=perception_job_id,
            filler_kind="actor",
            session=session,
        )

    async def create_feature_draft(
        self,
        project_id: int,
        owner_user_id: int,
        perception_job_id: int,
        session,
    ) -> dict:
        return await self._create_draft(
            project_id=project_id,
            owner_user_id=owner_user_id,
            perception_job_id=perception_job_id,
            filler_kind="feature",
            session=session,
        )

    async def create_scenario_draft(
        self,
        project_id: int,
        owner_user_id: int,
        perception_job_id: int,
        session,
    ) -> dict:
        return await self._create_draft(
            project_id=project_id,
            owner_user_id=owner_user_id,
            perception_job_id=perception_job_id,
            filler_kind="scenario",
            session=session,
        )

    async def create_acceptance_criteria_draft(
        self,
        project_id: int,
        owner_user_id: int,
        perception_job_id: int,
        session,
    ) -> dict:
        return await self._create_draft(
            project_id=project_id,
            owner_user_id=owner_user_id,
            perception_job_id=perception_job_id,
            filler_kind="acceptance_criteria",
            session=session,
        )

    async def create_flow_draft(
        self,
        project_id: int,
        owner_user_id: int,
        perception_job_id: int,
        session,
    ) -> dict:
        return await self._create_draft(
            project_id=project_id,
            owner_user_id=owner_user_id,
            perception_job_id=perception_job_id,
            filler_kind="flow",
            session=session,
        )

    async def _create_draft(
        self,
        project_id: int,
        owner_user_id: int,
        perception_job_id: int,
        filler_kind: str,
        session,
    ) -> dict:
        draft_id = uuid4().hex
        draft_payload, response_payload = await self._generate_preview(
            project_id=project_id,
            perception_job_id=perception_job_id,
            filler_kind=filler_kind,
            user_feedback=None,
            session=session,
        )

        draft_payload["draft_id"] = draft_id
        response_payload["draft_id"] = draft_id

        from backend.api.modules.decision_workflow.public import GenerativeDraftStore
        await GenerativeDraftStore.save_draft(
            project_id=project_id,
            draft_id=draft_id,
            draft_type="perception_slot_filling",
            payload=draft_payload,
            owner_user_id=owner_user_id,
            session=session,
        )

        return response_payload

    async def regenerate_draft(
        self,
        draft_id: str,
        owner_user_id: int,
        session,
        user_feedback: str | None = None,
    ) -> dict:
        draft = await self._get_draft(draft_id, owner_user_id, session)

        draft_payload, response_payload = await self._generate_preview(
            project_id=draft["project_id"],
            perception_job_id=draft["perception_job_id"],
            filler_kind=draft["filler_kind"],
            user_feedback=user_feedback,
            session=session,
        )

        draft_payload["draft_id"] = draft_id
        response_payload["draft_id"] = draft_id

        from backend.api.modules.decision_workflow.public import GenerativeDraftStore
        await GenerativeDraftStore.save_draft(
            project_id=draft["project_id"],
            draft_id=draft_id,
            draft_type="perception_slot_filling",
            payload=draft_payload,
            owner_user_id=owner_user_id,
            session=session,
        )

        return response_payload

    async def _get_draft(
        self,
        draft_id: str,
        owner_user_id: int,
        session,
    ) -> dict:
        from backend.api.modules.decision_workflow.public import GenerativeDraftStore
        return await GenerativeDraftStore.get_draft(draft_id, owner_user_id, session)

    async def _generate_preview(
        self,
        project_id: int,
        perception_job_id: int,
        filler_kind: str,
        user_feedback: str | None,
        session,
    ) -> tuple[dict, dict]:
        if filler_kind == "actor":
            return await PerceptionPreviewBuilder.generate_actor_preview(
                creator=self,
                project_id=project_id,
                perception_job_id=perception_job_id,
                user_feedback=user_feedback,
                session=session,
            )

        if filler_kind == "feature":
            return await PerceptionPreviewBuilder.generate_feature_preview(
                creator=self,
                project_id=project_id,
                perception_job_id=perception_job_id,
                user_feedback=user_feedback,
                session=session,
            )

        if filler_kind == "scenario":
            return await PerceptionPreviewBuilder.generate_scenario_preview(
                creator=self,
                project_id=project_id,
                perception_job_id=perception_job_id,
                user_feedback=user_feedback,
                session=session,
            )

        if filler_kind == "acceptance_criteria":
            return await PerceptionPreviewBuilder.generate_acceptance_criteria_preview(
                creator=self,
                project_id=project_id,
                perception_job_id=perception_job_id,
                user_feedback=user_feedback,
                session=session,
            )

        if filler_kind == "flow":
            return await PerceptionPreviewBuilder.generate_flow_preview(
                creator=self,
                project_id=project_id,
                perception_job_id=perception_job_id,
                user_feedback=user_feedback,
                session=session,
            )

        raise ValueError("unsupported_filler_kind")
