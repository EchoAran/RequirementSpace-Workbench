import hashlib
import json
import logging
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.generators.rules_generator import (
    RulesGenerator,
    RulesGeneratorInput,
)
from backend.core.logging.events import (
    RULE_DISCOVERY_COMPLETED,
    RULE_DISCOVERY_FAILED,
    RULE_DISCOVERY_STARTED,
)
from backend.core.observability import emit_how_lifecycle_event
from backend.database.model import (
    ActorModel,
    BranchWorkspaceModel,
    DomainRuleModel,
    FeatureModel,
    FeatureRelationModel,
    ProjectModel,
    ScenarioAcceptanceCriterionModel,
    ScenarioModel,
    feature_actor_table,
)
from backend.schemas import ActorNode, FeatureNode


class RuleGenerationService:
    """Application service for domain rule discovery and candidate generation."""

    def __init__(self):
        self._rules_generator = RulesGenerator()

    async def load_rule_generation_context(
        self,
        session: AsyncSession,
        project_id: int,
        workspace_id: int,
        user_feedback: str | None = None,
    ) -> tuple[RulesGeneratorInput, str]:
        user_reqs = await self._load_user_requirements(session, project_id, workspace_id)
        actors = await self._load_actors(session, project_id, workspace_id)
        features = await self._load_features(session, project_id, workspace_id)
        scenarios = await self._load_scenarios(session, project_id, workspace_id)
        acceptance_criteria = await self._load_acceptance_criteria(
            session, scenarios, workspace_id
        )
        existing_rules = await self._load_existing_rules(
            session, project_id, workspace_id
        )
        knowledge_query = f"{user_reqs}\n" + "\n".join(
            s.get("name", "") for s in scenarios
        )
        knowledge_fragments = await self._load_knowledge_fragments(
            session, project_id, knowledge_query
        )

        context_hash = self.compute_source_context_hash(
            user_requirements=user_reqs,
            actors=actors,
            features=features,
            scenarios=scenarios,
            acceptance_criteria=acceptance_criteria,
            existing_rules=existing_rules,
            knowledge_fragments=knowledge_fragments,
        )

        input_data = RulesGeneratorInput(
            user_requirements=user_reqs,
            actors=actors,
            features=features,
            scenarios=scenarios,
            acceptance_criteria=acceptance_criteria,
            existing_rules=existing_rules,
            knowledge_fragments=knowledge_fragments,
            user_feedback=user_feedback,
        )
        return input_data, context_hash

    async def generate_rules(
        self,
        session: AsyncSession,
        project_id: int,
        workspace_id: int,
        user_feedback: str | None = None,
    ) -> tuple[dict[str, Any], str]:
        emit_how_lifecycle_event(
            RULE_DISCOVERY_STARTED,
            capability="rule_discovery",
            project_id=project_id,
            workspace_id=workspace_id,
        )
        try:
            input_data, context_hash = await self.load_rule_generation_context(
                session=session,
                project_id=project_id,
                workspace_id=workspace_id,
                user_feedback=user_feedback,
            )
            result = await self._rules_generator.generate(input_data)
        except Exception as error:
            emit_how_lifecycle_event(
                RULE_DISCOVERY_FAILED,
                capability="rule_discovery",
                project_id=project_id,
                workspace_id=workspace_id,
                error_code=type(error).__name__,
                level=logging.ERROR,
            )
            raise
        emit_how_lifecycle_event(
            RULE_DISCOVERY_COMPLETED,
            capability="rule_discovery",
            project_id=project_id,
            workspace_id=workspace_id,
            rule_count=len(result.get("rules", [])),
        )
        return result, context_hash

    @staticmethod
    def compute_source_context_hash(
        user_requirements: str,
        actors: list[ActorNode],
        features: list[FeatureNode],
        scenarios: list[dict[str, Any]],
        acceptance_criteria: list[dict[str, Any]],
        existing_rules: list[dict[str, Any]],
        knowledge_fragments: list[dict[str, Any]] | None = None,
    ) -> str:
        data = {
            "reqs": (user_requirements or "").strip(),
            "actors": sorted(
                [{"id": a.actorId, "name": a.actorName} for a in actors],
                key=lambda x: x["id"],
            ),
            "features": sorted(
                [{"id": f.featureId, "name": f.featureName} for f in features],
                key=lambda x: x["id"],
            ),
            "scenarios": sorted(
                [
                    {
                        "uuid": s.get("logical_uuid"),
                        "name": s.get("name"),
                        "content": s.get("content"),
                    }
                    for s in scenarios
                ],
                key=lambda x: str(x["uuid"]),
            ),
            "ac": sorted(
                [
                    {
                        "uuid": ac.get("logical_uuid"),
                        "content": ac.get("content"),
                    }
                    for ac in acceptance_criteria
                ],
                key=lambda x: str(x["uuid"]),
            ),
            "rules": sorted(
                [
                    {
                        "uuid": r.get("logical_uuid"),
                        "title": r.get("title"),
                        "statement": r.get("statement"),
                    }
                    for r in existing_rules
                ],
                key=lambda x: str(x["uuid"]),
            ),
            "knowledge": sorted(
                [
                    {
                        "id": k.get("fragment_id"),
                        "content": k.get("content"),
                    }
                    for k in (knowledge_fragments or [])
                ],
                key=lambda x: str(x["id"]),
            ),
        }
        raw_json = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw_json.encode("utf-8")).hexdigest()

    @staticmethod
    async def _load_knowledge_fragments(
        session: AsyncSession,
        project_id: int,
        query: str,
    ) -> list[dict[str, Any]]:
        from backend.database.model import ProjectGenerationStrategyConfigModel

        stmt = sa.select(ProjectGenerationStrategyConfigModel).where(
            ProjectGenerationStrategyConfigModel.project_id == project_id
        )
        res = await session.execute(stmt)
        db_config = res.scalar_one_or_none()
        if db_config is not None and not db_config.knowledge_enabled:
            return []

        from backend.services.knowledge.retrieval import KnowledgeRetrievalService

        chunks = await KnowledgeRetrievalService.retrieve_chunks(
            session=session,
            query=query[:1000] if query else "domain rules business logic",
            project_id=project_id,
            top_n=10,
        )
        fragments = []
        for c in chunks:
            doc_name = c.document.original_filename if c.document is not None else "unknown"
            fragments.append(
                {
                    "fragment_id": f"chunk-{c.id}",
                    "document_id": c.document_id,
                    "document_name": doc_name,
                    "content": (c.text or "")[:300],
                }
            )
        return fragments

    @staticmethod
    async def _load_user_requirements(
        session: AsyncSession, project_id: int, workspace_id: int
    ) -> str:
        workspace = await session.get(BranchWorkspaceModel, workspace_id)
        if workspace is None or workspace.project_id != project_id:
            raise ValueError("project_not_found")
        return workspace.user_requirements

    @staticmethod
    async def _load_actors(
        session: AsyncSession, project_id: int, workspace_id: int
    ) -> list[ActorNode]:
        stmt = sa.select(ActorModel).where(ActorModel.project_id == project_id)
        stmt = stmt.where(ActorModel.workspace_id == workspace_id)
        res = await session.execute(stmt)
        return [
            ActorNode(
                actorId=a.id,
                actorName=a.name,
                actorDescription=a.description,
            )
            for a in res.scalars().all()
        ]

    @staticmethod
    async def _load_features(
        session: AsyncSession, project_id: int, workspace_id: int
    ) -> list[FeatureNode]:
        stmt = sa.select(FeatureModel).where(FeatureModel.project_id == project_id)
        stmt = stmt.where(FeatureModel.workspace_id == workspace_id)
        features = (await session.execute(stmt)).scalars().all()
        if not features:
            return []

        feature_ids = {f.id for f in features}
        rel_res = await session.execute(
            sa.select(FeatureRelationModel).where(
                FeatureRelationModel.parent_feature_id.in_(feature_ids)
            )
        )
        act_res = await session.execute(
            sa.select(
                feature_actor_table.c.feature_id,
                feature_actor_table.c.actor_id,
            ).where(feature_actor_table.c.feature_id.in_(feature_ids))
        )

        children_map: dict[int, list[int]] = {}
        parent_map: dict[int, int] = {}
        for rel in rel_res.scalars().all():
            children_map.setdefault(rel.parent_feature_id, []).append(
                rel.child_feature_id
            )
            parent_map[rel.child_feature_id] = rel.parent_feature_id

        actors_map: dict[int, list[int]] = {}
        for fid, aid in act_res.all():
            actors_map.setdefault(fid, []).append(aid)

        return [
            FeatureNode(
                featureId=f.id,
                featureName=f.name,
                featureDescription=f.description,
                actorIds=actors_map.get(f.id, []),
                parentId=parent_map.get(f.id),
                childrenIds=children_map.get(f.id, []),
            )
            for f in features
        ]

    @staticmethod
    async def _load_scenarios(
        session: AsyncSession, project_id: int, workspace_id: int
    ) -> list[dict[str, Any]]:
        stmt = sa.select(ScenarioModel).where(ScenarioModel.project_id == project_id)
        stmt = stmt.where(ScenarioModel.workspace_id == workspace_id)
        res = await session.execute(stmt)
        scenarios = res.scalars().all()
        return [
            {
                "id": s.id,
                "logical_uuid": s.logical_uuid,
                "name": s.name,
                "content": s.content,
                "feature_id": s.feature_id,
                "actor_id": s.actor_id,
                "confirmation_status": s.confirmation_status,
            }
            for s in scenarios
        ]

    @staticmethod
    async def _load_acceptance_criteria(
        session: AsyncSession,
        scenarios: list[dict[str, Any]],
        workspace_id: int,
    ) -> list[dict[str, Any]]:
        scenario_ids = [s["id"] for s in scenarios if "id" in s]
        if not scenario_ids:
            return []

        stmt = sa.select(ScenarioAcceptanceCriterionModel).where(
            ScenarioAcceptanceCriterionModel.scenario_id.in_(scenario_ids)
        )
        stmt = stmt.where(
            ScenarioAcceptanceCriterionModel.workspace_id == workspace_id
        )
        stmt = stmt.order_by(ScenarioAcceptanceCriterionModel.position.asc())
        res = await session.execute(stmt)
        acs = res.scalars().all()
        return [
            {
                "id": ac.id,
                "logical_uuid": ac.logical_uuid,
                "scenario_id": ac.scenario_id,
                "content": ac.content,
                "confirmation_status": ac.confirmation_status,
            }
            for ac in acs
        ]

    @staticmethod
    async def _load_existing_rules(
        session: AsyncSession, project_id: int, workspace_id: int
    ) -> list[dict[str, Any]]:
        stmt = sa.select(DomainRuleModel).where(
            DomainRuleModel.project_id == project_id
        )
        stmt = stmt.where(DomainRuleModel.workspace_id == workspace_id)
        res = await session.execute(stmt)
        rules = res.scalars().all()
        return [
            {
                "id": r.id,
                "logical_uuid": r.logical_uuid,
                "title": r.title,
                "statement": r.statement,
                "parent_rule_id": r.parent_rule_id,
                "confirmation_status": r.confirmation_status,
            }
            for r in rules
        ]
