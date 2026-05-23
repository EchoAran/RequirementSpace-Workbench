from sqlalchemy import select

from fastapi import BackgroundTasks

from backend.api.services.perception_job_service import PerceptionJobService
from backend.core.suggestions import (
    HowSuggestionPolicy,
    ScopeSuggestionPolicy,
    WhatSuggestionPolicy,
)
from backend.schemas import NextSuggestion


class NextSuggestionService:
    def __init__(self):
        self._policies = {
            "what": WhatSuggestionPolicy(),
            "how": HowSuggestionPolicy(),
            "scope": ScopeSuggestionPolicy(),
        }
        self._perception_job_service = PerceptionJobService()

    async def get_next_suggestion(
        self,
        project_id: int,
        stage: str,
        session,
        background_tasks: BackgroundTasks | None = None,
    ) -> dict:
        stage = self._normalize_stage(stage)

        policy = self._policies.get(stage)

        if policy is None:
            await self._ensure_project_exists(project_id, session)
            suggestion = NextSuggestion(
                sourceType="predefined",
                code="PREVIEW_READY",
                title="查看预览",
                description="当前已处于预览阶段。",
                action={
                    "kind": "navigate",
                    "route": f"/projects/{project_id}/preview",
                },
            ).to_dict()
        else:
            suggestion_node = await policy.get_next(
                project_id=project_id,
                session=session,
            )

            if stage == "what" and suggestion_node.code == "ENTER_HOW":
                perception_suggestion = await (
                    self._perception_job_service
                ).get_next_what_suggestion(
                    project_id=project_id,
                    session=session,
                    background_tasks=background_tasks,
                )

                if perception_suggestion is not None:
                    suggestion_node = perception_suggestion

            if stage == "how" and suggestion_node.code == "ENTER_SCOPE":
                perception_suggestion = await (
                    self._perception_job_service
                ).get_next_how_suggestion(
                    project_id=project_id,
                    session=session,
                    background_tasks=background_tasks,
                )

                if perception_suggestion is not None:
                    suggestion_node = perception_suggestion

            suggestion = suggestion_node.to_dict()

        return {
            "project_id": project_id,
            "stage": stage,
            "suggestion": suggestion,
        }

    async def start_next_suggestion(
        self,
        project_id: int,
        stage: str,
        suggestion_code: str,
        target: dict | None,
        query: str | None,
        session,
    ) -> dict:
        stage = self._normalize_stage(stage)
        await self._ensure_project_exists(project_id, session)

        action = self._build_start_action(
            project_id=project_id,
            suggestion_code=suggestion_code,
            target=target or {},
            query=query,
        )

        return {
            "project_id": project_id,
            "stage": stage,
            "suggestion_code": suggestion_code,
            "action_type": action["kind"],
            "action": action,
        }

    @staticmethod
    def _normalize_stage(stage: str) -> str:
        normalized_stage = stage.strip().lower()

        if normalized_stage not in {
            "what",
            "how",
            "scope",
            "preview",
        }:
            raise ValueError("invalid_stage")

        return normalized_stage

    @staticmethod
    async def _ensure_project_exists(project_id: int, session) -> None:
        from backend.database.model import ProjectModel

        project_result = await session.execute(
            select(ProjectModel.id).where(ProjectModel.id == project_id)
        )

        if project_result.scalar_one_or_none() is None:
            raise ValueError("project_not_found")

    @staticmethod
    def _build_start_action(
        project_id: int,
        suggestion_code: str,
        target: dict,
        query: str | None,
    ) -> dict:
        payload = {
            "project_id": project_id,
        }

        if query is not None:
            payload["query"] = query

        generator_action_map = {
            "GENERATE_ACTORS": (
                "actor_generation",
                "/api/actor_generation_drafts",
            ),
            "GENERATE_FEATURES": (
                "feature_generation",
                "/api/feature_generation_drafts",
            ),
            "GENERATE_SCENARIOS": (
                "scenario_generation",
                "/api/scenario_generation_drafts/full",
            ),
            "GENERATE_FLOWS_AND_BUSINESS_OBJECTS": (
                "flow_generation",
                "/api/flow_generation_drafts",
            ),
            "GENERATE_SCOPE": (
                "scope_generation",
                "/api/scope_generation_drafts",
            ),
        }

        generator_action = generator_action_map.get(suggestion_code)

        if generator_action is not None:
            draft_type, endpoint = generator_action
            return {
                "kind": "create_draft",
                "draft_type": draft_type,
                "endpoint": endpoint,
                "payload": payload,
            }

        if suggestion_code == "ENTER_HOW":
            return {
                "kind": "navigate",
                "route": f"/projects/{project_id}/how",
            }

        if suggestion_code == "ENTER_SCOPE":
            return {
                "kind": "navigate",
                "route": f"/projects/{project_id}/scope",
            }

        if suggestion_code == "ENTER_PREVIEW":
            return {
                "kind": "navigate",
                "route": f"/projects/{project_id}/preview",
            }

        if suggestion_code.endswith("_PERCEPTION_RUNNING"):
            return {
                "kind": "wait",
            }

        if suggestion_code.endswith("_PERCEPTION_FAILED"):
            return {
                "kind": "retry",
                "payload": target,
            }

        if suggestion_code.endswith("_SLOT"):
            # Slot filler draft generation is intentionally a separate step:
            # the first action opens the target panel and lets the user choose
            # manual handling or AI filling.
            route_stage = "how" if suggestion_code == "FLOW_SLOT" else "what"
            return {
                "kind": "open_panel",
                "route": f"/projects/{project_id}/{route_stage}",
                "panel": "perception_slot",
                "payload": target,
            }

        raise ValueError("unsupported_suggestion_code")
