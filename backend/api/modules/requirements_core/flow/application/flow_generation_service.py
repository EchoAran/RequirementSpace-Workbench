import re
from uuid import uuid4
from sqlalchemy import select

from backend.core.notifier import get_notifier
from backend.core.generators.flows_generator import (
    FlowsGenerator,
    FlowsGeneratorInput,
)
from backend.schemas import ActorNode, FeatureNode
from .generation import (
    build_flow_generation_response,
    load_flow_generation_context,
    persist_flow_generation_draft,
    validate_generated_flows,
)


class FlowGenerationService:
    # Below 8 leaves, one-shot generation keeps fewer LLM calls and enough context.
    _three_step_leaf_feature_threshold = 8
    _business_object_number_pattern = re.compile(
        r"^B-\d{3}$"
    )
    _step_number_pattern = re.compile(
        r"^S-\d{3}$"
    )
    _valid_step_types = {
        "actorAction",
        "systemAction",
        "judgment",
    }

    def __init__(self):
        self._flows_generator = FlowsGenerator()

    async def create_draft(
        self,
        project_id: int,
        owner_user_id: int,
        session,
        branch_name: str | None = None,
        head_commit_id: str | None = None,
        workspace_id: int | None = None,
    ) -> dict:
        draft_id = uuid4().hex
        draft_payload, response_payload = await self._generate_preview(
            project_id=project_id,
            user_feedback=None,
            session=session,
            workspace_id=workspace_id,
        )
        draft_payload["draft_id"] = draft_id
        draft_payload["branch_name"] = branch_name
        draft_payload["head_commit_id"] = head_commit_id
        response_payload["draft_id"] = draft_id
        response_payload["branch_name"] = branch_name
        response_payload["head_commit_id"] = head_commit_id

        from backend.api.modules.decision_workflow.public import GenerativeDraftStore
        await GenerativeDraftStore.save_draft(
            project_id=project_id,
            draft_id=draft_id,
            draft_type="flow",
            payload=draft_payload,
            owner_user_id=owner_user_id,
            session=session,
        )

        return response_payload

    async def regenerate_draft(
        self,
        draft_id: str,
        owner_user_id: int,
        user_feedback: str | None,
        session,
    ) -> dict:
        draft = await self._get_draft(draft_id, owner_user_id, session)

        draft_payload, response_payload = await self._generate_preview(
            project_id=draft["project_id"],
            user_feedback=user_feedback,
            session=session,
        )

        draft_payload["draft_id"] = draft_id
        draft_payload["branch_name"] = draft.get("branch_name")
        draft_payload["head_commit_id"] = draft.get("head_commit_id")
        response_payload["draft_id"] = draft_id
        response_payload["branch_name"] = draft.get("branch_name")
        response_payload["head_commit_id"] = draft.get("head_commit_id")

        from backend.api.modules.decision_workflow.public import GenerativeDraftStore
        await GenerativeDraftStore.save_draft(
            project_id=draft["project_id"],
            draft_id=draft_id,
            draft_type="flow",
            payload=draft_payload,
            owner_user_id=owner_user_id,
            session=session,
        )

        return response_payload

    async def confirm_draft(
        self,
        draft_id: str,
        owner_user_id: int,
        session,
        branch_name: str | None = None,
        head_commit_id: str | None = None,
        workspace_id: int | None = None,
    ) -> dict:
        draft = await self._get_draft(draft_id, owner_user_id, session)

        draft_branch = draft.get("branch_name")
        if draft_branch and branch_name and draft_branch != branch_name:
            raise ValueError(f"draft_branch_mismatch: Draft created on branch '{draft_branch}' cannot be confirmed on '{branch_name}'")

        draft_commit = draft.get("head_commit_id")
        if draft_commit and head_commit_id and draft_commit != head_commit_id:
            raise ValueError("branch_drift_detected: Branch head commit has advanced since draft creation")

        result = await self._persist_flow_generation_draft(
            draft=draft,
            session=session,
            workspace_id=workspace_id,
        )
        await get_notifier().mark_stale(
            project_id=draft["project_id"],
            stages={"how"},
            perception_kinds={"FLOW"},
            session=session,
        )

        from backend.api.modules.decision_workflow.public import GenerativeDraftStore
        await GenerativeDraftStore.delete_draft(draft_id, owner_user_id, session)

        return result

    async def discard_draft(
        self,
        draft_id: str,
        owner_user_id: int,
    ) -> dict:
        from backend.api.modules.decision_workflow.public import GenerativeDraftStore
        await GenerativeDraftStore.discard_draft_locally(draft_id, owner_user_id)

        return {
            "draft_id": draft_id,
            "message": "draft_discarded",
        }

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
        user_feedback: str | None,
        session,
    ) -> tuple[dict, dict]:
        (
            raw,
            actor_nodes,
            feature_nodes,
            leaf_feature_count,
            use_three_step_generation,
        ) = await self.generate_raw(
            project_id=project_id,
            user_feedback=user_feedback,
            session=session,
        )

        draft_payload = {
            "project_id": project_id,
            "generation_mode": (
                "three_step"
                if use_three_step_generation
                else "single_step"
            ),
            "leaf_feature_count": leaf_feature_count,
            "business_objects": raw["business_objects"],
            "flows": raw["flows"],
        }

        response_payload = self._build_response_payload(
            project_id=project_id,
            draft_payload=draft_payload,
            actor_nodes=actor_nodes,
            feature_nodes=feature_nodes,
        )

        return draft_payload, response_payload

    async def generate_raw(
        self,
        project_id: int,
        user_feedback: str | None,
        session,
        validate_result: bool = True,
    ) -> tuple[dict, list[ActorNode], list[FeatureNode], int, bool]:
        (
            user_requirements,
            actor_nodes,
            feature_nodes,
            leaf_feature_count,
        ) = await self._load_project_context(
            project_id=project_id,
            session=session,
        )
        use_three_step_generation = (
            leaf_feature_count >= self._three_step_leaf_feature_threshold
        )

        raw = await self._flows_generator.generate(
            FlowsGeneratorInput(
                user_requirements=user_requirements,
                actors=actor_nodes,
                features=feature_nodes,
                user_feedback=user_feedback,
            ),
            use_combined_prompt=not use_three_step_generation,
        )
        if validate_result:
            self._validate_generated_flows(
                raw=raw,
                actor_nodes=actor_nodes,
                feature_nodes=feature_nodes,
            )

        return (
            raw,
            actor_nodes,
            feature_nodes,
            leaf_feature_count,
            use_three_step_generation,
        )

    @staticmethod
    async def _load_project_context(
        project_id: int,
        session,
    ) -> tuple[str, list[ActorNode], list[FeatureNode], int]:
        return await load_flow_generation_context(project_id, session)

    def _validate_generated_flows(
        self,
        raw: dict,
        actor_nodes: list[ActorNode],
        feature_nodes: list[FeatureNode],
    ) -> None:
        validate_generated_flows(
            raw,
            actor_nodes,
            feature_nodes,
            business_object_number_pattern=(
                self._business_object_number_pattern
            ),
            step_number_pattern=self._step_number_pattern,
            valid_step_types=self._valid_step_types,
        )

    @staticmethod
    def _build_response_payload(
        project_id: int,
        draft_payload: dict,
        actor_nodes: list[ActorNode],
        feature_nodes: list[FeatureNode],
    ) -> dict:
        return build_flow_generation_response(
            project_id,
            draft_payload,
            actor_nodes,
            feature_nodes,
        )

    @staticmethod
    async def _persist_flow_generation_draft(
        draft: dict,
        session,
    ) -> dict:
        return await persist_flow_generation_draft(draft, session)
