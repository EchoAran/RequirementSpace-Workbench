from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from backend.core.localized_messages import localized_message
from backend.api.modules.preview_convergence.ports.preview_generator import (
    PrototypePageGeneratorPort,
    get_page_generator,
)
from backend.api.modules.preview_convergence.schemas.prototype import (
    PrototypePageResponse,
    PrototypePreviewResponse,
)
from backend.api.modules.project_lifecycle.public import ProjectService
from backend.core.generators.prototype_generator import (
    PrototypeGeneratorInput,
    PrototypePageGeneratorInput,
)
from backend.core.security import sanitize_message
from backend.database.model import GherkinSpecModel, ProjectModel, PrototypePreviewModel
from backend.schemas import (
    AcceptanceCriterionNode,
    ActorNode,
    BusinessObjectAttributeNode,
    BusinessObjectNode,
    FeatureNode,
    FlowNode,
    FlowStepNode,
    ScenarioNode,
)


@dataclass
class PrototypeGenerationContext:
    targets: list[dict[str, Any]]
    input_snapshot: dict[str, Any]
    gherkin_snapshot: dict[str, Any] | None


class PrototypeGenerationService:
    def __init__(
        self,
        session_factory=None,
        page_generator: PrototypePageGeneratorPort | None = None,
    ) -> None:
        self._project_service = ProjectService()
        from backend.database.database import AsyncSessionLocal
        self.session_factory = session_factory or AsyncSessionLocal
        self._page_generator = page_generator
        self._background_tasks: dict[int, asyncio.Task] = {}

    async def start_generation(
        self,
        project_id: int,
        force_regenerate: bool = False,
    ) -> PrototypePreviewResponse:
        async with self.session_factory() as session:
            latest = await self.get_latest_preview(
                project_id=project_id,
                session=session,
                raise_if_missing=False,
            )
            if latest is not None and (
                latest.status == "generating" or not force_regenerate
            ):
                if latest.status == "generating":
                    self.ensure_generation_running(latest.prototype_id, project_id)
                return latest

            preview = PrototypePreviewModel(
                project_id=project_id,
                status="generating",
                source=self._preview_source(),
                html="",
                javascript="",
                css="",
                pages=[],
                input_snapshot={},
            )
            session.add(preview)
            await session.commit()

            from sqlalchemy.orm import selectinload
            result = await session.execute(
                select(PrototypePreviewModel)
                .options(selectinload(PrototypePreviewModel.project))
                .where(PrototypePreviewModel.id == preview.id)
            )
            preview = result.scalar_one()
            response = self._to_response(preview)

        self.ensure_generation_running(response.prototype_id, project_id)
        return response

    def ensure_generation_running(self, preview_id: int, project_id: int) -> None:
        existing = self._background_tasks.get(preview_id)
        if existing is not None and not existing.done():
            return

        task = asyncio.create_task(
            self._complete_generation(preview_id, project_id)
        )
        self._background_tasks[preview_id] = task

        def discard_completed(completed: asyncio.Task) -> None:
            if self._background_tasks.get(preview_id) is completed:
                self._background_tasks.pop(preview_id, None)
            if not completed.cancelled():
                completed.exception()

        task.add_done_callback(discard_completed)

    async def _complete_generation(self, preview_id: int, project_id: int) -> None:
        try:
            async with self.session_factory() as session:
                context = await self._load_generation_context(project_id, session)

            pages = await self._generate_pages(context.targets)
            first_page = pages[0]

            async with self.session_factory() as session:
                preview = await session.get(PrototypePreviewModel, preview_id)
                if preview is None:
                    return
                preview.status = "ready"
                preview.source = self._preview_source()
                preview.html = first_page["html"]
                preview.javascript = first_page["javascript"]
                preview.css = first_page["css"]
                preview.pages = pages
                preview.input_snapshot = context.input_snapshot
                preview.gherkin_snapshot = context.gherkin_snapshot
                preview.error_message = ""
                await session.commit()
        except Exception as error:
            logging.getLogger(__name__).exception(
                "Prototype generation failed for project %s", project_id
            )
            async with self.session_factory() as session:
                preview = await session.get(PrototypePreviewModel, preview_id)
                if preview is None:
                    return
                preview.status = "failed"
                preview.error_message = sanitize_message(
                    str(error) or type(error).__name__
                )
                await session.commit()

    async def generate_preview(
        self,
        project_id: int,
        force_regenerate: bool = False,
    ) -> PrototypePreviewResponse:
        if not force_regenerate:
            async with self.session_factory() as session:
                latest = await self.get_latest_preview(
                    project_id=project_id,
                    session=session,
                    raise_if_missing=False,
                )
                if latest is not None:
                    return latest

        async with self.session_factory() as session:
            context = await self._load_generation_context(project_id, session)

        pages = await self._generate_pages(context.targets)
        
        async with self.session_factory() as session:
            try:
                preview = self._build_preview_model(
                    project_id=project_id,
                    context=context,
                    pages=pages,
                )
                session.add(preview)
                await session.commit()
                
                from sqlalchemy.orm import selectinload
                result = await session.execute(
                    select(PrototypePreviewModel)
                    .options(selectinload(PrototypePreviewModel.project))
                    .where(PrototypePreviewModel.id == preview.id)
                )
                preview = result.scalar_one()
                response = self._to_response(preview)
            except Exception:
                await session.rollback()
                raise
        return response

    async def _load_generation_context(
        self,
        project_id: int,
        session,
    ) -> PrototypeGenerationContext:
        detail = await self._project_service.get_project_detail(
            project_id=project_id,
            session=session,
        )
        gherkin_specs = await self._load_gherkin_specs(
            project_id=project_id,
            session=session,
        )

        generator_input = self._build_generator_input(
            detail=detail,
            gherkin_specs=gherkin_specs,
        )
        targets = self._build_role_feature_targets(
            generator_input=generator_input,
            detail=detail,
        )
        
        input_snapshot = detail.model_dump(
            mode="json",
            by_alias=True,
        )
        gherkin_snapshot = {"specs": gherkin_specs} if gherkin_specs else None

        return PrototypeGenerationContext(
            targets=targets,
            input_snapshot=input_snapshot,
            gherkin_snapshot=gherkin_snapshot,
        )

    async def _generate_pages(
        self,
        targets: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not targets:
            raise ValueError("prototype_targets_empty")
        generator = self._page_generator or get_page_generator()
        if generator is None:
            raise RuntimeError("prototype_generator_unavailable")
        return await generator.generate_pages(targets)

    def _preview_source(self) -> str:
        generator = self._page_generator or get_page_generator()
        if generator is None:
            raise RuntimeError("prototype_generator_unavailable")
        return generator.preview_source()

    def _build_preview_model(
        self,
        project_id: int,
        context: PrototypeGenerationContext,
        pages: list[dict[str, Any]],
    ) -> PrototypePreviewModel:
        if not pages:
            raise ValueError("prototype_targets_empty")
        first_page = pages[0]
        return PrototypePreviewModel(
            project_id=project_id,
            status="ready",
            source=self._preview_source(),
            html=first_page["html"],
            javascript=first_page["javascript"],
            css=first_page["css"],
            pages=pages,
            input_snapshot=context.input_snapshot,
            gherkin_snapshot=context.gherkin_snapshot,
        )

    async def get_latest_preview(
        self,
        project_id: int,
        session,
        raise_if_missing: bool = True,
    ) -> PrototypePreviewResponse | None:
        project_exists = await session.scalar(
            select(ProjectModel.id).where(ProjectModel.id == project_id)
        )
        if project_exists is None:
            raise ValueError("project_not_found")
        from sqlalchemy.orm import selectinload
        result = await session.execute(
            select(PrototypePreviewModel)
            .options(selectinload(PrototypePreviewModel.project))
            .where(PrototypePreviewModel.project_id == project_id)
            .order_by(PrototypePreviewModel.created_at.desc())
            .limit(1)
        )
        preview = result.scalar_one_or_none()
        if preview is None:
            if raise_if_missing:
                raise ValueError("prototype_preview_not_found")
            return None
        return self._to_response(preview)

    @staticmethod
    async def _load_gherkin_specs(
        project_id: int,
        session,
    ) -> list[dict]:
        result = await session.execute(
            select(GherkinSpecModel)
            .where(GherkinSpecModel.project_id == project_id)
            .order_by(GherkinSpecModel.created_at.asc())
        )
        specs = result.scalars().all()
        return [
            {
                "id": spec.id,
                "feature_id": spec.feature_id,
                "actor_id": spec.actor_id,
                "source": spec.source,
                "gherkin_json": spec.gherkin_json,
            }
            for spec in specs
        ]

    @classmethod
    def _build_role_feature_targets(
        cls,
        generator_input: PrototypeGeneratorInput,
        detail,
    ) -> list[dict[str, Any]]:
        actors_by_id = {
            actor.actorId: actor
            for actor in generator_input.actors
        }
        feature_details_by_id = {
            feature.feature_id: feature
            for feature in detail.features
        }
        leaf_features = [
            feature
            for feature in generator_input.features
            if not feature.childrenIds
        ]
        if any(item.scope is not None for item in detail.features):
            leaf_features = [
                feature
                for feature in leaf_features
                if (
                    feature_details_by_id.get(feature.featureId) is not None
                    and feature_details_by_id[feature.featureId].scope is not None
                    and feature_details_by_id[feature.featureId].scope.scope_status == "current"
                )
            ]

        targets: list[dict[str, Any]] = []
        for feature in leaf_features:
            feature_detail = feature_details_by_id.get(feature.featureId)
            role_ids = set(feature.actorIds)
            role_ids.update(
                scenario.actorId
                for scenario in feature.scenarios
                if scenario.actorId is not None
            )

            for actor_id in sorted(role_ids):
                actor = actors_by_id.get(actor_id)
                if actor is None:
                    continue
                scenarios = [
                    scenario
                    for scenario in feature.scenarios
                    if scenario.actorId == actor_id
                ] or list(feature.scenarios)
                acceptance_criteria = cls._acceptance_criteria_for_target(
                    actor=actor,
                    feature=feature,
                    scenarios=scenarios,
                    feature_detail=feature_detail,
                )
                targets.append(
                    {
                        "page_id": f"role-{actor.actorId}-feature-{feature.featureId}",
                        "actor": actor,
                        "feature": feature,
                        "acceptance_criteria": acceptance_criteria,
                        "input": PrototypePageGeneratorInput(
                            project_id=generator_input.project_id,
                            project_name=generator_input.project_name,
                            project_description=generator_input.project_description,
                            user_requirements=generator_input.user_requirements,
                            actor=actor,
                            feature=feature,
                            scenarios=scenarios,
                            business_objects=generator_input.business_objects,
                            flows=[
                                flow
                                for flow in generator_input.flows
                                if feature.featureId in flow.featureIds
                            ],
                            acceptance_criteria=acceptance_criteria,
                        ),
                    }
                )

        if targets:
            return targets

        if generator_input.actors and generator_input.features:
            actor = generator_input.actors[0]
            feature = generator_input.features[0]
            acceptance_criteria = cls._acceptance_criteria_for_target(
                actor=actor,
                feature=feature,
                scenarios=feature.scenarios,
                feature_detail=feature_details_by_id.get(feature.featureId),
            )
            return [
                {
                    "page_id": f"role-{actor.actorId}-feature-{feature.featureId}",
                    "actor": actor,
                    "feature": feature,
                    "acceptance_criteria": acceptance_criteria,
                    "input": PrototypePageGeneratorInput(
                        project_id=generator_input.project_id,
                        project_name=generator_input.project_name,
                        project_description=generator_input.project_description,
                        user_requirements=generator_input.user_requirements,
                        actor=actor,
                        feature=feature,
                        scenarios=feature.scenarios,
                        business_objects=generator_input.business_objects,
                        flows=generator_input.flows,
                        acceptance_criteria=acceptance_criteria,
                    ),
                }
            ]

        return []

    @staticmethod
    def _acceptance_criteria_for_target(
        actor: ActorNode,
        feature: FeatureNode,
        scenarios: list[ScenarioNode],
        feature_detail,
    ) -> dict[str, Any]:
        scenario_items = []
        for scenario in scenarios:
            criteria_text = " ".join(
                criterion.criterionContent
                for criterion in scenario.acceptanceCriteria
            ).strip()
            scenario_items.append(
                {
                    "Scenario": scenario.scenarioName,
                    "Given": scenario.scenarioContent,
                    "When": f"{actor.actorName} uses {feature.featureName}",
                    "Then": criteria_text
                    or "the system provides the expected result",
                }
            )

        if not scenario_items:
            scenario_items.append(
                {
                    "Scenario": localized_message(
                        "prototype_scenario_name",
                        actor=actor.actorName,
                        feature=feature.featureName,
                    ),
                    "Given": feature.featureDescription,
                    "When": f"{actor.actorName} opens this function",
                    "Then": "the role can complete the target task",
                }
            )

        actor_names = [actor.actorName]
        if feature_detail is not None:
            actor_names = [
                actor_name
                for actor_name in getattr(feature_detail, "actor_names", []) or []
            ] or actor_names

        return {
            "Features": [
                {
                    "Feature": feature.featureName,
                    "Narrative": {
                        "As": ", ".join(actor_names),
                        "I want": feature.featureName,
                        "So that": feature.featureDescription,
                    },
                    "Scenarios": scenario_items,
                }
            ]
        }

    @staticmethod
    def _page_payload(
        target: dict[str, Any],
        code: dict[str, str],
        source: str,
    ) -> dict[str, Any]:
        actor = target["actor"]
        feature = target["feature"]
        return {
            "page_id": target["page_id"],
            "role_id": actor.actorId,
            "role_name": actor.actorName,
            "feature_id": feature.featureId,
            "feature_name": feature.featureName,
            "html": code.get("HTML", ""),
            "javascript": code.get("Javascript", ""),
            "css": code.get("CSS", ""),
            "source": source,
            "status": "ready",
        }

    @staticmethod
    def _build_generator_input(
        detail,
        gherkin_specs: list[dict],
    ) -> PrototypeGeneratorInput:
        actors = [
            ActorNode(
                actorId=actor.actor_id,
                actorName=actor.actor_name,
                actorDescription=actor.actor_description,
            )
            for actor in detail.actors
        ]

        scenarios_by_feature: dict[int, list[ScenarioNode]] = {}
        all_scenarios: list[ScenarioNode] = []
        for feature in detail.features:
            feature_scenarios = []
            for scenario in feature.scenarios:
                criteria = [
                    AcceptanceCriterionNode(
                        criterionId=criterion.criterion_id,
                        criterionContent=criterion.criterion_content,
                    )
                    for criterion in scenario.acceptance_criteria
                ]
                node = ScenarioNode(
                    scenarioId=scenario.scenario_id,
                    scenarioName=scenario.scenario_name,
                    scenarioContent=scenario.scenario_content,
                    featureId=scenario.feature_id,
                    actorId=scenario.actor_id,
                    acceptanceCriteria=criteria,
                )
                feature_scenarios.append(node)
                all_scenarios.append(node)
            scenarios_by_feature[feature.feature_id] = feature_scenarios

        features = [
            FeatureNode(
                featureId=feature.feature_id,
                featureName=feature.feature_name,
                featureDescription=feature.feature_description,
                actorIds=feature.actor_ids,
                parentId=feature.parent_id,
                childrenIds=feature.children_ids,
                scenarios=scenarios_by_feature.get(feature.feature_id, []),
            )
            for feature in detail.features
        ]

        business_objects = [
            BusinessObjectNode(
                businessObjectId=item.business_object_id,
                businessObjectName=item.business_object_name,
                businessObjectDescription=item.business_object_description,
                businessObjectAttributes=[
                    BusinessObjectAttributeNode(
                        businessObjectAttributeId=attribute.business_object_attribute_id,
                        businessObjectAttributeName=attribute.business_object_attribute_name,
                        businessObjectAttributeDescription=attribute.business_object_attribute_description,
                        businessObjectAttributeType=attribute.business_object_attribute_type,
                        businessObjectAttributeExample=attribute.business_object_attribute_example,
                    )
                    for attribute in item.business_object_attributes
                ],
            )
            for item in detail.business_objects
        ]

        flows = [
            FlowNode(
                flowId=flow.flow_id,
                flowName=flow.flow_name,
                flowDescription=flow.flow_description,
                featureIds=flow.feature_ids,
                flowSteps=[
                    FlowStepNode(
                        stepId=step.step_id,
                        stepName=step.step_name,
                        stepDescription=step.step_description,
                        stepType=step.step_type,
                        actorIds=step.actor_ids,
                        inputBusinessObjectIds=step.input_business_object_ids,
                        outputBusinessObjectIds=step.output_business_object_ids,
                        nextStepIds=step.next_step_ids,
                    )
                    for step in flow.flow_steps
                ],
            )
            for flow in detail.flows
        ]

        return PrototypeGeneratorInput(
            project_id=detail.project_id,
            project_name=detail.project_name,
            project_description=detail.project_description,
            user_requirements=detail.user_requirements,
            actors=actors,
            features=features,
            scenarios=all_scenarios,
            business_objects=business_objects,
            flows=flows,
            gherkin_specs=gherkin_specs,
        )

    @staticmethod
    def _to_response(preview: PrototypePreviewModel) -> PrototypePreviewResponse:
        pages = [
            PrototypePageResponse(**page)
            for page in (preview.pages or [])
        ]
        project_id = str(preview.project_id)
        if preview.project is not None:
            project_id = preview.project.public_id
        return PrototypePreviewResponse(
            prototype_id=preview.id,
            project_id=project_id,
            html=preview.html,
            javascript=preview.javascript,
            css=preview.css,
            pages=pages,
            source=preview.source,
            status=preview.status,
            error_message=preview.error_message or None,
            created_at=preview.created_at,
            updated_at=preview.updated_at,
        )
