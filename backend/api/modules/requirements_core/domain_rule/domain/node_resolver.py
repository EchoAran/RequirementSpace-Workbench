"""Requirement node resolver for validating and resolving RuleLink targets."""

from dataclasses import dataclass
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.modules.requirements_core.domain_rule.domain.model_invariants import (
    ALLOWED_RULE_LINK_TARGET_KINDS,
)
from backend.core.logging.events import RULE_LINK_ORPHAN_DETECTED
from backend.core.observability import emit_how_lifecycle_event
from backend.database.model import (
    FeatureModel,
    FlowModel,
    FlowStepModel,
    FlowTransitionModel,
    KnowledgeChunkModel,
    KnowledgeDocumentModel,
    RuleLinkModel,
    ScenarioAcceptanceCriterionModel,
    ScenarioModel,
)


@dataclass(frozen=True)
class ResolvedNode:
    """Descriptor for a validated target entity linked to a domain rule."""

    kind: str
    logical_uuid: str
    entity_id: int
    display_name: str
    project_id: int
    workspace_id: int


class RequirementNodeResolver:
    """Validates existence and workspace scoping of specification nodes linked to domain rules."""

    @staticmethod
    def _apply_workspace_filter(query: Any, model: Any, workspace_id: int) -> Any:
        return query.where(model.workspace_id == workspace_id)

    async def resolve_target(
        self,
        session: AsyncSession,
        project_id: int,
        target_kind: str,
        target_logical_uuid: str,
        workspace_id: int,
    ) -> ResolvedNode:
        """Resolve and validate a target entity for rule linking.

        Raises ValueError if the target_kind is unsupported, or if the entity does
        not exist within the specified project and workspace scope.
        """
        if target_kind not in ALLOWED_RULE_LINK_TARGET_KINDS:
            raise ValueError(
                f"Unsupported target kind '{target_kind}'. Allowed: {sorted(ALLOWED_RULE_LINK_TARGET_KINDS)}"
            )

        if not target_logical_uuid or not target_logical_uuid.strip():
            raise ValueError("Target logical UUID cannot be empty.")

        target_uuid = target_logical_uuid.strip()

        if target_kind == "feature":
            stmt = sa.select(FeatureModel).where(
                FeatureModel.project_id == project_id,
                FeatureModel.logical_uuid == target_uuid,
            )
            stmt = self._apply_workspace_filter(stmt, FeatureModel, workspace_id)
            feature = (await session.execute(stmt)).scalar_one_or_none()
            if not feature:
                raise ValueError(
                    f"Feature target with logical UUID '{target_uuid}' not found in project {project_id}."
                )
            return ResolvedNode(
                kind=target_kind,
                logical_uuid=target_uuid,
                entity_id=feature.id,
                display_name=feature.name,
                project_id=project_id,
                workspace_id=workspace_id,
            )

        if target_kind == "scenario":
            stmt = sa.select(ScenarioModel).where(
                ScenarioModel.project_id == project_id,
                ScenarioModel.logical_uuid == target_uuid,
            )
            stmt = self._apply_workspace_filter(stmt, ScenarioModel, workspace_id)
            scenario = (await session.execute(stmt)).scalar_one_or_none()
            if not scenario:
                raise ValueError(
                    f"Scenario target with logical UUID '{target_uuid}' not found in project {project_id}."
                )
            return ResolvedNode(
                kind=target_kind,
                logical_uuid=target_uuid,
                entity_id=scenario.id,
                display_name=scenario.name,
                project_id=project_id,
                workspace_id=workspace_id,
            )

        if target_kind == "acceptance_criterion":
            stmt = (
                sa.select(ScenarioAcceptanceCriterionModel, ScenarioModel.name)
                .join(ScenarioModel, ScenarioAcceptanceCriterionModel.scenario_id == ScenarioModel.id)
                .where(
                    ScenarioModel.project_id == project_id,
                    ScenarioAcceptanceCriterionModel.logical_uuid == target_uuid,
                )
            )
            stmt = self._apply_workspace_filter(stmt, ScenarioAcceptanceCriterionModel, workspace_id)
            row = (await session.execute(stmt)).first()
            if not row:
                raise ValueError(
                    f"Acceptance criterion target with logical UUID '{target_uuid}' not found in project {project_id}."
                )
            ac, scenario_name = row
            return ResolvedNode(
                kind=target_kind,
                logical_uuid=target_uuid,
                entity_id=ac.id,
                display_name=f"AC #{ac.position} ({scenario_name})",
                project_id=project_id,
                workspace_id=workspace_id,
            )

        if target_kind == "flow":
            stmt = sa.select(FlowModel).where(
                FlowModel.project_id == project_id,
                FlowModel.logical_uuid == target_uuid,
            )
            stmt = self._apply_workspace_filter(stmt, FlowModel, workspace_id)
            flow = (await session.execute(stmt)).scalar_one_or_none()
            if not flow:
                raise ValueError(
                    f"Flow target with logical UUID '{target_uuid}' not found in project {project_id}."
                )
            return ResolvedNode(
                kind=target_kind,
                logical_uuid=target_uuid,
                entity_id=flow.id,
                display_name=flow.name,
                project_id=project_id,
                workspace_id=workspace_id,
            )

        if target_kind == "flow_step":
            stmt = (
                sa.select(FlowStepModel, FlowModel.name)
                .join(FlowModel, FlowStepModel.flow_id == FlowModel.id)
                .where(
                    FlowModel.project_id == project_id,
                    FlowStepModel.logical_uuid == target_uuid,
                )
            )
            stmt = self._apply_workspace_filter(stmt, FlowStepModel, workspace_id)
            row = (await session.execute(stmt)).first()
            if not row:
                raise ValueError(
                    f"Flow step target with logical UUID '{target_uuid}' not found in project {project_id}."
                )
            step, flow_name = row
            return ResolvedNode(
                kind=target_kind,
                logical_uuid=target_uuid,
                entity_id=step.id,
                display_name=f"{step.name} ({flow_name})",
                project_id=project_id,
                workspace_id=workspace_id,
            )

        if target_kind == "flow_transition":
            stmt = (
                sa.select(FlowTransitionModel, FlowModel.name)
                .join(FlowModel, FlowTransitionModel.flow_id == FlowModel.id)
                .where(
                    FlowModel.project_id == project_id,
                    FlowTransitionModel.logical_uuid == target_uuid,
                )
            )
            stmt = self._apply_workspace_filter(stmt, FlowTransitionModel, workspace_id)
            row = (await session.execute(stmt)).first()
            if not row:
                raise ValueError(
                    f"Flow transition target with logical UUID '{target_uuid}' not found in project {project_id}."
                )
            trans, flow_name = row
            return ResolvedNode(
                kind=target_kind,
                logical_uuid=target_uuid,
                entity_id=trans.id,
                display_name=f"Transition #{trans.id} ({flow_name})",
                project_id=project_id,
                workspace_id=workspace_id,
            )

        if target_kind == "knowledge":
            chunk_id = None
            if target_uuid.startswith("chunk-") and target_uuid[6:].isdigit():
                chunk_id = int(target_uuid[6:])
            elif target_uuid.isdigit():
                chunk_id = int(target_uuid)

            if chunk_id is None:
                raise ValueError(
                    f"Invalid knowledge chunk target identifier '{target_uuid}'."
                )

            stmt = (
                sa.select(KnowledgeChunkModel, KnowledgeDocumentModel.original_filename)
                .join(
                    KnowledgeDocumentModel,
                    KnowledgeChunkModel.document_id == KnowledgeDocumentModel.id,
                )
                .where(
                    KnowledgeChunkModel.id == chunk_id,
                    KnowledgeChunkModel.project_id == project_id,
                )
            )
            row = (await session.execute(stmt)).first()
            if not row:
                raise ValueError(
                    f"Knowledge chunk target with ID '{target_uuid}' not found in project {project_id}."
                )
            chunk, doc_name = row
            return ResolvedNode(
                kind=target_kind,
                logical_uuid=target_uuid,
                entity_id=chunk.id,
                display_name=f"Knowledge Chunk #{chunk.id}"
                + (f" ({doc_name})" if doc_name else ""),
                project_id=project_id,
                workspace_id=workspace_id,
            )

        raise ValueError(f"Unhandled target kind '{target_kind}'.")

    async def sweep_orphaned_links(
        self,
        session: AsyncSession,
        project_id: int,
        workspace_id: int,
    ) -> int:
        """Find and remove rule links whose target entities no longer exist."""
        stmt = sa.select(RuleLinkModel).where(RuleLinkModel.project_id == project_id)
        stmt = self._apply_workspace_filter(stmt, RuleLinkModel, workspace_id)
        links = (await session.execute(stmt)).scalars().all()

        deleted_count = 0
        for link in links:
            try:
                await self.resolve_target(
                    session=session,
                    project_id=project_id,
                    target_kind=link.target_kind,
                    target_logical_uuid=link.target_logical_uuid,
                    workspace_id=workspace_id,
                )
            except ValueError:
                await session.delete(link)
                deleted_count += 1

        if deleted_count > 0:
            await session.flush()
            emit_how_lifecycle_event(
                RULE_LINK_ORPHAN_DETECTED,
                capability="rule_link_integrity",
                project_id=project_id,
                workspace_id=workspace_id,
                orphan_count=deleted_count,
            )
        return deleted_count

    async def delete_links_for_targets(
        self,
        session: AsyncSession,
        project_id: int,
        target_kind: str,
        target_logical_uuids: list[str],
        workspace_id: int,
    ) -> int:
        """Explicitly delete rule links pointing to the specified target logical UUIDs."""
        if not target_logical_uuids:
            return 0
        stmt = (
            sa.delete(RuleLinkModel)
            .where(
                RuleLinkModel.project_id == project_id,
                RuleLinkModel.target_kind == target_kind,
                RuleLinkModel.target_logical_uuid.in_(target_logical_uuids),
            )
        )
        stmt = stmt.where(RuleLinkModel.workspace_id == workspace_id)
        res = await session.execute(stmt)
        await session.flush()
        return res.rowcount or 0
