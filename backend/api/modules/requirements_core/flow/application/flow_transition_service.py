"""Application service for managing flow transitions.

This module orchestrates CRUD operations, optimistic concurrency control,
default edge arbitration, rule link associations, and perception invalidation
for FlowTransition entities.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.modules.requirements_core.domain_rule.application.domain_rule_service import DomainRuleService
from backend.api.modules.requirements_core.flow.domain.model_invariants import (
    normalize_semantic_tags,
    validate_no_self_loop,
    validate_transition_flow_boundary,
    validate_transition_labels,
    validate_transition_position,
)
from backend.api.modules.requirements_core.flow.schemas import (
    FlowTransitionCreateRequest,
    FlowTransitionResponse,
    FlowTransitionUpdateRequest,
)
from backend.core.notifier import RequirementsChangedNotifier, get_notifier
from backend.database.model import (
    DomainRuleModel,
    FlowModel,
    FlowStepModel,
    FlowTransitionModel,
    RuleLinkModel,
)


class FlowTransitionService:
    """Service handling lifecycle and operations on flow transitions."""

    def __init__(self, stale_notifier: RequirementsChangedNotifier | None = None) -> None:
        self._stale_notifier = stale_notifier

    async def _notify_stale(
        self,
        project_id: int,
        session: AsyncSession,
        workspace_id: int,
        changed_targets: list[tuple[str, str]] | None = None,
    ) -> None:
        """Notify How perception using the injected or registered notifier."""
        notifier = self._stale_notifier if self._stale_notifier is not None else get_notifier()
        await notifier.mark_stale(
            project_id=project_id,
            stages={"how"},
            session=session,
            workspace_id=workspace_id,
            changed_targets=changed_targets,
        )

    async def create_transition(
        self,
        project_id: int,
        flow_id: int,
        request: FlowTransitionCreateRequest,
        session: AsyncSession,
        workspace_id: int,
    ) -> FlowTransitionResponse:
        """Create a new transition edge connecting two steps in a flow.

        Args:
            project_id: Owning project ID.
            flow_id: Owning flow ID.
            request: Transition creation payload.
            session: Database session.
            workspace_id: Branch workspace ID.

        Returns:
            Created FlowTransitionResponse.

        Raises:
            HTTPException: If steps are not found, or cross-boundary rules are violated.
        """
        # Validate no direct self-loops
        try:
            validate_no_self_loop(request.source_step_id, request.target_step_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        # Verify flow exists in project and workspace
        flow_stmt = select(FlowModel).where(
            FlowModel.id == flow_id,
            FlowModel.project_id == project_id,
            FlowModel.workspace_id == workspace_id,
        )
        flow_res = await session.execute(flow_stmt)
        flow = flow_res.scalar_one_or_none()
        if not flow:
            raise HTTPException(
                status_code=404,
                detail=f"Flow {flow_id} not found in project {project_id}",
            )

        # Load source and target steps with flow and workspace scoping
        stmt = select(FlowStepModel).where(
            FlowStepModel.id.in_([request.source_step_id, request.target_step_id]),
            FlowStepModel.flow_id == flow_id,
            FlowStepModel.workspace_id == workspace_id,
        )
        steps_result = await session.execute(stmt)
        steps = {s.id: s for s in steps_result.scalars().all()}

        source_step = steps.get(request.source_step_id)
        target_step = steps.get(request.target_step_id)

        if not source_step:
            raise HTTPException(
                status_code=404,
                detail=f"Source step {request.source_step_id} not found",
            )
        if not target_step:
            raise HTTPException(
                status_code=404,
                detail=f"Target step {request.target_step_id} not found",
            )

        # Validate flow, project, and workspace boundaries
        try:
            validate_transition_flow_boundary(
                source_flow_id=source_step.flow_id,
                target_flow_id=target_step.flow_id,
                expected_flow_id=flow_id,
                source_project_id=flow.project_id,
                target_project_id=flow.project_id,
                expected_project_id=project_id,
                source_workspace_id=source_step.workspace_id,
                target_workspace_id=target_step.workspace_id,
                expected_workspace_id=workspace_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        # Check for duplicate edge
        dup_stmt = select(FlowTransitionModel).where(
            FlowTransitionModel.source_step_id == request.source_step_id,
            FlowTransitionModel.target_step_id == request.target_step_id,
            FlowTransitionModel.workspace_id == workspace_id,
        )
        dup_res = await session.execute(dup_stmt)
        if dup_res.scalar_one_or_none():
            raise HTTPException(
                status_code=409,
                detail=f"Transition from step {request.source_step_id} to {request.target_step_id} already exists",
            )

        # Validate rule_ids belonging to project and workspace
        if request.rule_ids:
            rule_set = set(request.rule_ids)
            rule_stmt = select(DomainRuleModel.id).where(
                DomainRuleModel.id.in_(rule_set),
                DomainRuleModel.project_id == project_id,
                DomainRuleModel.workspace_id == workspace_id,
            )
            rule_res = await session.execute(rule_stmt)
            found_rule_ids = set(rule_res.scalars().all())
            missing_rules = rule_set - found_rule_ids
            if missing_rules:
                raise HTTPException(
                    status_code=400,
                    detail=f"Rules {missing_rules} not found in project or workspace",
                )

        # Clean strings and normalize tags
        label, condition = validate_transition_labels(request.label, request.condition_text)
        tags = normalize_semantic_tags(request.semantic_tags)

        # Determine edge position and reorder siblings if collision occurs
        sib_stmt = (
            select(FlowTransitionModel)
            .where(
                FlowTransitionModel.source_step_id == request.source_step_id,
                FlowTransitionModel.workspace_id == workspace_id,
            )
            .order_by(FlowTransitionModel.position.asc(), FlowTransitionModel.id.asc())
        )
        sib_res = await session.execute(sib_stmt)
        siblings = list(sib_res.scalars().all())

        if request.position is None:
            max_pos = max((s.position for s in siblings), default=-1)
            position = max_pos + 1
        else:
            try:
                validate_transition_position(request.position)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

            target_pos = min(request.position, len(siblings))
            if any(s.position == target_pos for s in siblings):
                # Two-phase shift to avoid uq_flow_transition_source_position collision
                for idx, s in enumerate(siblings):
                    s.position = -(idx + 1000)
                await session.flush()

                for idx, s in enumerate(siblings):
                    s.position = idx if idx < target_pos else idx + 1
                await session.flush()
            position = target_pos

        # Arbitrate default exclusivity: reset existing default for same source
        if request.is_default:
            await session.execute(
                update(FlowTransitionModel)
                .where(
                    FlowTransitionModel.source_step_id == request.source_step_id,
                    FlowTransitionModel.workspace_id == workspace_id,
                )
                .values(is_default=False)
            )

        transition = FlowTransitionModel(
            project_id=project_id,
            workspace_id=workspace_id,
            flow_id=flow_id,
            source_step_id=request.source_step_id,
            target_step_id=request.target_step_id,
            label=label,
            condition_text=condition,
            is_default=request.is_default,
            position=position,
            semantic_tags=tags,
            origin=request.origin,
            confirmation_status=request.confirmation_status,
        )
        session.add(transition)
        await session.flush()

        # Associate rule IDs via RuleLinkModel
        if request.rule_ids:
            for rule_id in set(request.rule_ids):
                link = RuleLinkModel(
                    project_id=project_id,
                    workspace_id=workspace_id,
                    rule_id=rule_id,
                    target_kind="flow_transition",
                    target_logical_uuid=transition.logical_uuid,
                )
                session.add(link)
            await session.flush()

        await self._notify_stale(
            project_id,
            session,
            workspace_id,
            changed_targets=[("flow_transition", transition.logical_uuid)],
        )

        return await self._build_response(transition, session)

    async def update_transition(
        self,
        project_id: int,
        flow_id: int,
        transition_id: int,
        request: FlowTransitionUpdateRequest,
        session: AsyncSession,
        workspace_id: int,
    ) -> FlowTransitionResponse:
        """Update an existing transition with optimistic concurrency protection.

        Args:
            project_id: Owning project ID.
            flow_id: Owning flow ID.
            transition_id: ID of the transition to update.
            request: Update fields.
            session: Database session.
            workspace_id: Branch workspace ID.

        Returns:
            Updated FlowTransitionResponse.

        Raises:
            HTTPException: 404 if not found, 409 on version conflict.
        """
        stmt = select(FlowTransitionModel).where(
            FlowTransitionModel.id == transition_id,
            FlowTransitionModel.flow_id == flow_id,
            FlowTransitionModel.project_id == project_id,
            FlowTransitionModel.workspace_id == workspace_id,
        )
        result = await session.execute(stmt)
        transition = result.scalar_one_or_none()
        if not transition:
            raise HTTPException(status_code=404, detail="Flow transition not found")

        # Optimistic concurrency check
        if request.last_seen_updated_at is not None:
            if transition.updated_at and transition.updated_at != request.last_seen_updated_at:
                raise HTTPException(
                    status_code=409,
                    detail="Transition has been modified by another operation",
                )

        if request.label is not None:
            transition.label = request.label.strip()

        if request.condition_text is not None:
            transition.condition_text = request.condition_text.strip()

        if request.semantic_tags is not None:
            transition.semantic_tags = normalize_semantic_tags(request.semantic_tags)

        if request.position is not None:
            try:
                validate_transition_position(request.position)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

            # Fetch all siblings sharing source_step_id within the workspace
            sib_stmt = (
                select(FlowTransitionModel)
                .where(
                    FlowTransitionModel.source_step_id == transition.source_step_id,
                    FlowTransitionModel.workspace_id == workspace_id,
                )
                .order_by(FlowTransitionModel.position.asc(), FlowTransitionModel.id.asc())
            )
            sib_res = await session.execute(sib_stmt)
            siblings = list(sib_res.scalars().all())

            other_siblings = [s for s in siblings if s.id != transition.id]
            target_pos = min(request.position, len(other_siblings))
            new_order = [*other_siblings[:target_pos], transition, *other_siblings[target_pos:]]

            # Two-phase flush: temporary negative offsets then normalized indices
            for idx, s in enumerate(new_order):
                s.position = -(idx + 1000)
            await session.flush()

            for idx, s in enumerate(new_order):
                s.position = idx
            await session.flush()

        if request.confirmation_status is not None:
            transition.confirmation_status = request.confirmation_status

        if request.is_default is not None:
            if request.is_default and not transition.is_default:
                # Reset other default transitions for this source
                await session.execute(
                    update(FlowTransitionModel)
                    .where(
                        FlowTransitionModel.source_step_id == transition.source_step_id,
                        FlowTransitionModel.workspace_id == workspace_id,
                        FlowTransitionModel.id != transition.id,
                    )
                    .values(is_default=False)
                )
            transition.is_default = request.is_default

        # Update Rule links if specified
        if request.rule_ids is not None:
            try:
                await DomainRuleService().replace_target_rules(
                    session, project_id, "flow_transition", transition.logical_uuid,
                    request.rule_ids, workspace_id,
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        transition.updated_at = datetime.now(UTC)
        await session.flush()

        await self._notify_stale(
            project_id,
            session,
            workspace_id,
            changed_targets=[("flow_transition", transition.logical_uuid)],
        )

        return await self._build_response(transition, session)

    async def delete_transition(
        self,
        project_id: int,
        flow_id: int,
        transition_id: int,
        session: AsyncSession,
        workspace_id: int,
    ) -> None:
        """Delete a flow transition and its associated rule links.

        Args:
            project_id: Owning project ID.
            flow_id: Owning flow ID.
            transition_id: Target transition ID.
            session: Database session.
            workspace_id: Branch workspace ID.
        """
        stmt = select(FlowTransitionModel).where(
            FlowTransitionModel.id == transition_id,
            FlowTransitionModel.flow_id == flow_id,
            FlowTransitionModel.project_id == project_id,
            FlowTransitionModel.workspace_id == workspace_id,
        )
        res = await session.execute(stmt)
        transition = res.scalar_one_or_none()
        if not transition:
            raise HTTPException(status_code=404, detail="Flow transition not found")

        target_uuid = transition.logical_uuid

        # Clean associated rule links
        await session.execute(
            delete(RuleLinkModel).where(
                RuleLinkModel.target_kind == "flow_transition",
                RuleLinkModel.target_logical_uuid == target_uuid,
                RuleLinkModel.project_id == project_id,
                RuleLinkModel.workspace_id == workspace_id,
            )
        )

        source_step_id = transition.source_step_id
        await session.delete(transition)
        await session.flush()

        remaining_siblings = list(
            (
                await session.execute(
                    select(FlowTransitionModel)
                    .where(
                        FlowTransitionModel.source_step_id == source_step_id,
                        FlowTransitionModel.workspace_id == workspace_id,
                    )
                    .order_by(FlowTransitionModel.position.asc(), FlowTransitionModel.id.asc())
                )
            ).scalars().all()
        )
        if remaining_siblings:
            for idx, s in enumerate(remaining_siblings):
                s.position = -(idx + 1000)
            await session.flush()
            for idx, s in enumerate(remaining_siblings):
                s.position = idx
            await session.flush()

        await self._notify_stale(
            project_id,
            session,
            workspace_id,
            changed_targets=[("flow_transition", target_uuid)],
        )

    async def get_transition(
        self,
        project_id: int,
        flow_id: int,
        transition_id: int,
        session: AsyncSession,
        workspace_id: int,
    ) -> FlowTransitionResponse:
        """Retrieve a transition by ID."""
        stmt = select(FlowTransitionModel).where(
            FlowTransitionModel.id == transition_id,
            FlowTransitionModel.flow_id == flow_id,
            FlowTransitionModel.project_id == project_id,
            FlowTransitionModel.workspace_id == workspace_id,
        )
        res = await session.execute(stmt)
        transition = res.scalar_one_or_none()
        if not transition:
            raise HTTPException(status_code=404, detail="Flow transition not found")
        return await self._build_response(transition, session)

    async def list_transitions(
        self,
        project_id: int,
        flow_id: int,
        session: AsyncSession,
        workspace_id: int,
    ) -> list[FlowTransitionResponse]:
        """List all transitions belonging to a flow."""
        stmt = (
            select(FlowTransitionModel)
            .where(
                FlowTransitionModel.flow_id == flow_id,
                FlowTransitionModel.project_id == project_id,
                FlowTransitionModel.workspace_id == workspace_id,
            )
            .order_by(FlowTransitionModel.position, FlowTransitionModel.id)
        )
        res = await session.execute(stmt)
        transitions = res.scalars().all()

        responses = []
        for t in transitions:
            responses.append(await self._build_response(t, session))
        return responses

    async def _build_response(
        self,
        transition: FlowTransitionModel,
        session: AsyncSession,
    ) -> FlowTransitionResponse:
        """Build FlowTransitionResponse with associated rule IDs."""
        links_stmt = select(RuleLinkModel.rule_id).where(
            RuleLinkModel.target_kind == "flow_transition",
            RuleLinkModel.link_purpose == "applies_to",
            RuleLinkModel.target_logical_uuid == transition.logical_uuid,
            RuleLinkModel.project_id == transition.project_id,
            RuleLinkModel.workspace_id == transition.workspace_id,
        )
        links_res = await session.execute(links_stmt)
        rule_ids = list(links_res.scalars().all())

        return FlowTransitionResponse(
            id=transition.id,
            logical_uuid=transition.logical_uuid,
            project_id=transition.project_id,
            workspace_id=transition.workspace_id,
            flow_id=transition.flow_id,
            source_step_id=transition.source_step_id,
            target_step_id=transition.target_step_id,
            label=transition.label,
            condition_text=transition.condition_text,
            is_default=transition.is_default,
            position=transition.position,
            semantic_tags=transition.semantic_tags or [],
            origin=transition.origin,
            confirmation_status=transition.confirmation_status,
            rule_ids=rule_ids,
            created_at=transition.created_at,
            updated_at=transition.updated_at,
        )
