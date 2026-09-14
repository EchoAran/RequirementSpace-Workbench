"""Application service orchestrating DomainRule and RuleLink lifecycle."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.modules.optimistic_lock.snapshot_service import snapshot_service
from backend.api.modules.requirements_core.domain_rule.domain.model_invariants import (
    validate_parent_hierarchy,
    validate_rule_confirmation_status,
    validate_rule_link_purpose,
    validate_rule_link_target,
    validate_rule_origin,
    validate_rule_text,
)
from backend.api.modules.requirements_core.domain_rule.domain.node_resolver import (
    RequirementNodeResolver,
)
from backend.api.modules.requirements_core.domain_rule.schemas import (
    DomainRuleCreateRequest,
    DomainRuleUpdateRequest,
    RuleLinkCreateRequest,
    RuleLinkUpdateRequest,
)
from backend.database.model import ConfirmationStatus, DomainRuleModel, RuleLinkModel
from backend.services.audit_service import AuditService

audit_service = AuditService()


class DomainRuleService:
    """Provides use cases for creating, querying, updating, and linking domain rules."""

    @staticmethod
    def _apply_workspace_filter(query, model, workspace_id: int):
        """Apply workspace filtering supporting both branch workspaces and default workspace."""
        return query.where(model.workspace_id == workspace_id)

    async def list_rules(
        self,
        session: AsyncSession,
        project_id: int,
        workspace_id: int,
        confirmation_status: str | None = None,
        origin: str | None = None,
    ) -> tuple[Sequence[DomainRuleModel], int]:
        """Fetch domain rules matching the provided criteria along with total count."""
        stmt = (
            sa.select(DomainRuleModel)
            .where(DomainRuleModel.project_id == project_id)
            .options(
                selectinload(DomainRuleModel.links),
                selectinload(DomainRuleModel.child_rules),
            )
            .order_by(DomainRuleModel.id.asc())
            .execution_options(populate_existing=True)
        )
        stmt = self._apply_workspace_filter(stmt, DomainRuleModel, workspace_id)

        if confirmation_status:
            stmt = stmt.where(DomainRuleModel.confirmation_status == confirmation_status)
        if origin:
            stmt = stmt.where(DomainRuleModel.origin == origin)

        result = await session.execute(stmt)
        rules = result.scalars().all()
        return rules, len(rules)

    async def get_rule(
        self,
        session: AsyncSession,
        project_id: int,
        rule_id: int,
        workspace_id: int,
    ) -> DomainRuleModel | None:
        """Load a single domain rule with links and child rules preloaded."""
        stmt = (
            sa.select(DomainRuleModel)
            .where(DomainRuleModel.project_id == project_id, DomainRuleModel.id == rule_id)
            .options(
                selectinload(DomainRuleModel.links),
                selectinload(DomainRuleModel.child_rules),
            )
            .execution_options(populate_existing=True)
        )
        stmt = self._apply_workspace_filter(stmt, DomainRuleModel, workspace_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def _collect_ancestor_ids(
        self,
        session: AsyncSession,
        project_id: int,
        parent_id: int | None,
        workspace_id: int,
    ) -> set[int]:
        """Traverse upward through parent links to identify all ancestor IDs."""
        ancestors: set[int] = set()
        current_id = parent_id
        while current_id is not None:
            ancestors.add(current_id)
            stmt = sa.select(DomainRuleModel.parent_rule_id).where(
                DomainRuleModel.project_id == project_id,
                DomainRuleModel.id == current_id,
            )
            stmt = self._apply_workspace_filter(stmt, DomainRuleModel, workspace_id)
            parent_result = (await session.execute(stmt)).scalar_one_or_none()
            if parent_result is None or parent_result in ancestors:
                break
            current_id = parent_result
        return ancestors

    async def create_rule(
        self,
        session: AsyncSession,
        project_id: int,
        request: DomainRuleCreateRequest,
        workspace_id: int,
    ) -> DomainRuleModel:
        """Create and persist a new domain rule after validating domain invariants."""
        validate_rule_text(request.title, request.statement)
        validate_rule_origin(request.origin)
        validate_rule_confirmation_status(request.confirmation_status)

        if request.parent_rule_id is not None:
            parent = await self.get_rule(session, project_id, request.parent_rule_id, workspace_id)
            if not parent:
                raise ValueError(f"Parent rule ID {request.parent_rule_id} does not exist in workspace.")

        rule = DomainRuleModel(
            project_id=project_id,
            workspace_id=workspace_id,
            title=request.title.strip(),
            statement=request.statement.strip(),
            origin=request.origin,
            confirmation_status=request.confirmation_status,
            parent_rule_id=request.parent_rule_id,
        )
        session.add(rule)
        await session.flush()

        await audit_service.record(
            session=session,
            project_id=project_id,
            action_type="create_domain_rule",
            summary=f"Create domain rule: {rule.title}",
            target_type="domain_rule",
            target_id=rule.id,
            diff={
                "title": rule.title,
                "statement": rule.statement,
                "origin": rule.origin,
                "confirmation_status": rule.confirmation_status,
            },
        )

        await self._notify_rule_change(session, project_id, workspace_id)
        return await self.get_rule(session, project_id, rule.id, workspace_id)  # type: ignore

    async def _notify_rule_change(
        self,
        session: AsyncSession,
        project_id: int,
        workspace_id: int,
    ) -> None:
        """Trigger perception stale notification for HOW phase when rules change."""
        from backend.core.notifier import get_notifier

        await get_notifier().mark_stale(
            project_id=project_id,
            stages={"how"},
            perception_kinds={"RULE", "FLOW"},
            session=session,
            workspace_id=workspace_id,
        )

    async def update_rule(
        self,
        session: AsyncSession,
        project_id: int,
        rule_id: int,
        request: DomainRuleUpdateRequest,
        workspace_id: int,
    ) -> DomainRuleModel:
        """Update domain rule attributes ensuring invariants and acyclic parent relationships."""
        rule = await self.get_rule(session, project_id, rule_id, workspace_id)
        if not rule:
            raise ValueError(f"Domain rule {rule_id} not found.")

        if request.last_seen_updated_at is not None:
            await snapshot_service.check_optimistic_lock(
                session, "domain_rule", rule, request.last_seen_updated_at
            )

        new_title = request.title if request.title is not None else rule.title
        new_statement = request.statement if request.statement is not None else rule.statement
        validate_rule_text(new_title, new_statement)

        text_modified = new_title.strip() != rule.title or new_statement.strip() != rule.statement

        if request.origin is not None:
            validate_rule_origin(request.origin)
            rule.origin = request.origin

        if request.confirmation_status is not None:
            validate_rule_confirmation_status(request.confirmation_status)
            rule.confirmation_status = request.confirmation_status
        elif text_modified and rule.confirmation_status == ConfirmationStatus.CONFIRMED.value:
            rule.confirmation_status = ConfirmationStatus.NEEDS_CONFIRMATION.value

        if request.parent_rule_id is not None:
            parent = await self.get_rule(session, project_id, request.parent_rule_id, workspace_id)
            if not parent:
                raise ValueError(f"Parent rule ID {request.parent_rule_id} does not exist in workspace.")
            ancestors = await self._collect_ancestor_ids(
                session, project_id, request.parent_rule_id, workspace_id
            )
            validate_parent_hierarchy(rule_id, request.parent_rule_id, ancestors)
            rule.parent_rule_id = request.parent_rule_id
        elif "parent_rule_id" in request.model_fields_set and request.parent_rule_id is None:
            rule.parent_rule_id = None

        rule.title = new_title.strip()
        rule.statement = new_statement.strip()
        await session.flush()

        await audit_service.record(
            session=session,
            project_id=project_id,
            action_type="update_domain_rule",
            summary=f"Update domain rule: {rule.title}",
            target_type="domain_rule",
            target_id=rule.id,
            diff={
                "title": rule.title,
                "statement": rule.statement,
                "origin": rule.origin,
                "confirmation_status": rule.confirmation_status,
            },
        )

        await self._notify_rule_change(session, project_id, workspace_id)
        return rule

    async def delete_rule(
        self,
        session: AsyncSession,
        project_id: int,
        rule_id: int,
        workspace_id: int,
    ) -> bool:
        """Delete a domain rule and cascade its links, setting child rules' parent to null."""
        rule = await self.get_rule(session, project_id, rule_id, workspace_id)
        if not rule:
            return False
        stmt_unbind = (
            sa.update(DomainRuleModel)
            .where(
                DomainRuleModel.project_id == project_id,
                DomainRuleModel.parent_rule_id == rule_id,
            )
            .values(parent_rule_id=None)
        )
        stmt_unbind = self._apply_workspace_filter(stmt_unbind, DomainRuleModel, workspace_id)
        await session.execute(stmt_unbind)
        title = rule.title
        await session.delete(rule)
        await session.flush()

        await audit_service.record(
            session=session,
            project_id=project_id,
            action_type="delete_domain_rule",
            summary=f"Delete domain rule: {title}",
            target_type="domain_rule",
            target_id=rule_id,
            diff={"title": title},
        )

        await self._notify_rule_change(session, project_id, workspace_id)
        return True

    async def replace_target_rules(
        self,
        session: AsyncSession,
        project_id: int,
        target_kind: str,
        target_logical_uuid: str,
        rule_ids: list[int],
        workspace_id: int,
    ) -> None:
        """Update direct applies_to links atomically, retaining evidence and unchanged links."""
        if target_kind not in {"flow", "flow_step", "flow_transition"}:
            raise ValueError(f"Unsupported rule association target: {target_kind}")
        target = await RequirementNodeResolver().resolve_target(
            session, project_id, target_kind, target_logical_uuid, workspace_id,
        )
        requested = set(rule_ids)
        rules_stmt = self._apply_workspace_filter(
            sa.select(DomainRuleModel.id).where(
                DomainRuleModel.project_id == project_id,
                DomainRuleModel.id.in_(requested),
            ), DomainRuleModel, workspace_id,
        )
        found = set((await session.execute(rules_stmt)).scalars().all())
        if requested - found:
            raise ValueError(f"Rules not found in project or workspace: {sorted(requested - found)}")
        links_stmt = self._apply_workspace_filter(
            sa.select(RuleLinkModel).where(
                RuleLinkModel.project_id == project_id,
                RuleLinkModel.target_kind == target_kind,
                RuleLinkModel.target_logical_uuid == target.logical_uuid,
                RuleLinkModel.link_purpose == "applies_to",
            ), RuleLinkModel, workspace_id,
        )
        existing = list((await session.execute(links_stmt)).scalars().all())
        for link in existing:
            if link.rule_id not in requested:
                await session.delete(link)
        for rule_id in sorted(requested - {link.rule_id for link in existing}):
            session.add(RuleLinkModel(
                project_id=project_id, workspace_id=workspace_id, rule_id=rule_id,
                target_kind=target_kind, target_logical_uuid=target.logical_uuid,
                link_purpose="applies_to", context_text="",
            ))
        await session.flush()
        await audit_service.record(
            session=session, project_id=project_id, action_type="update_rule_link",
            summary=f"Update rules applying to {target_kind}:{target.logical_uuid}",
            target_type=target_kind, target_id=target.entity_id,
            diff={"rule_ids_before": sorted(link.rule_id for link in existing),
                  "rule_ids_after": sorted(requested)},
        )
        await self._notify_rule_change(session, project_id, workspace_id)

    async def create_link(
        self,
        session: AsyncSession,
        project_id: int,
        rule_id: int,
        request: RuleLinkCreateRequest,
        workspace_id: int,
    ) -> RuleLinkModel:
        """Attach a link from the domain rule to a target specification entity."""
        validate_rule_link_target(request.target_kind, request.target_logical_uuid)
        validate_rule_link_purpose(request.link_purpose)

        rule = await self.get_rule(session, project_id, rule_id, workspace_id)
        if not rule:
            raise ValueError(f"Domain rule {rule_id} not found.")

        resolver = RequirementNodeResolver()
        await resolver.resolve_target(
            session=session,
            project_id=project_id,
            target_kind=request.target_kind,
            target_logical_uuid=request.target_logical_uuid,
            workspace_id=workspace_id,
        )

        stmt_dup = sa.select(RuleLinkModel).where(
            RuleLinkModel.project_id == project_id,
            RuleLinkModel.rule_id == rule_id,
            RuleLinkModel.target_kind == request.target_kind,
            RuleLinkModel.target_logical_uuid == request.target_logical_uuid.strip(),
            RuleLinkModel.link_purpose == request.link_purpose,
        )
        stmt_dup = self._apply_workspace_filter(stmt_dup, RuleLinkModel, workspace_id)
        existing = (await session.execute(stmt_dup)).scalar_one_or_none()
        if existing:
            raise ValueError(
                f"Rule link already exists for rule {rule_id} and target {request.target_kind}:{request.target_logical_uuid}."
            )

        link = RuleLinkModel(
            project_id=project_id,
            workspace_id=workspace_id,
            rule_id=rule_id,
            target_kind=request.target_kind,
            target_logical_uuid=request.target_logical_uuid.strip(),
            link_purpose=request.link_purpose,
            context_text=request.context_text.strip(),
        )
        session.add(link)
        await session.flush()

        await audit_service.record(
            session=session,
            project_id=project_id,
            action_type="create_rule_link",
            summary=f"Create rule link from rule {rule_id} to {link.target_kind}:{link.target_logical_uuid}",
            target_type="rule_link",
            target_id=link.id,
            diff={
                "rule_id": rule_id,
                "target_kind": link.target_kind,
                "target_logical_uuid": link.target_logical_uuid,
                "link_purpose": link.link_purpose,
            },
        )

        await self._notify_rule_change(session, project_id, workspace_id)
        return link

    async def delete_link(
        self,
        session: AsyncSession,
        project_id: int,
        rule_id: int,
        link_id: int,
        workspace_id: int,
    ) -> bool:
        """Remove a rule link by its ID."""
        stmt = sa.select(RuleLinkModel).where(
            RuleLinkModel.project_id == project_id,
            RuleLinkModel.rule_id == rule_id,
            RuleLinkModel.id == link_id,
        )
        stmt = self._apply_workspace_filter(stmt, RuleLinkModel, workspace_id)
        link = (await session.execute(stmt)).scalar_one_or_none()
        if not link:
            return False
        await session.delete(link)
        await session.flush()

        await audit_service.record(
            session=session,
            project_id=project_id,
            action_type="delete_rule_link",
            summary=f"Delete rule link {link_id} from rule {rule_id}",
            target_type="rule_link",
            target_id=link_id,
        )

        await self._notify_rule_change(session, project_id, workspace_id)
        return True

    async def update_link(
        self,
        session: AsyncSession,
        project_id: int,
        rule_id: int,
        link_id: int,
        request: RuleLinkUpdateRequest,
        workspace_id: int,
    ) -> RuleLinkModel:
        """Update a scoped rule link without inferring its target or purpose."""
        query = sa.select(RuleLinkModel).where(
            RuleLinkModel.project_id == project_id,
            RuleLinkModel.rule_id == rule_id,
            RuleLinkModel.id == link_id,
        )
        query = self._apply_workspace_filter(query, RuleLinkModel, workspace_id)
        link = (await session.execute(query)).scalar_one_or_none()
        if link is None:
            raise ValueError(f"Rule link {link_id} not found.")
        if request.last_seen_updated_at is not None:
            await snapshot_service.check_optimistic_lock(
                session,
                "rule_link",
                link,
                request.last_seen_updated_at,
            )

        target_kind = request.target_kind or link.target_kind
        target_uuid = (
            request.target_logical_uuid.strip()
            if request.target_logical_uuid is not None
            else link.target_logical_uuid
        )
        purpose = request.link_purpose or link.link_purpose
        validate_rule_link_target(target_kind, target_uuid)
        validate_rule_link_purpose(purpose)
        await RequirementNodeResolver().resolve_target(
            session=session,
            project_id=project_id,
            target_kind=target_kind,
            target_logical_uuid=target_uuid,
            workspace_id=workspace_id,
        )

        duplicate_query = sa.select(RuleLinkModel).where(
            RuleLinkModel.project_id == project_id,
            RuleLinkModel.rule_id == rule_id,
            RuleLinkModel.target_kind == target_kind,
            RuleLinkModel.target_logical_uuid == target_uuid,
            RuleLinkModel.link_purpose == purpose,
            RuleLinkModel.id != link_id,
        )
        duplicate_query = self._apply_workspace_filter(
            duplicate_query,
            RuleLinkModel,
            workspace_id,
        )
        if (await session.execute(duplicate_query)).scalar_one_or_none() is not None:
            raise ValueError("Rule link already exists for this target and purpose.")

        link.target_kind = target_kind
        link.target_logical_uuid = target_uuid
        link.link_purpose = purpose
        if request.context_text is not None:
            link.context_text = request.context_text.strip()
        await session.flush()
        await audit_service.record(
            session=session,
            project_id=project_id,
            action_type="update_rule_link",
            summary=f"Update rule link {link.logical_uuid}",
            target_type="rule_link",
            target_id=link.id,
            diff={
                "logical_uuid": link.logical_uuid,
                "target_kind": target_kind,
                "target_logical_uuid": target_uuid,
                "link_purpose": purpose,
                "context_text": link.context_text,
            },
        )
        await self._notify_rule_change(session, project_id, workspace_id)
        return link

    async def list_links_for_target(
        self,
        session: AsyncSession,
        project_id: int,
        target_kind: str,
        target_logical_uuid: str,
        workspace_id: int,
    ) -> Sequence[RuleLinkModel]:
        """Find all links pointing to a specific target node."""
        stmt = (
            sa.select(RuleLinkModel)
            .where(
                RuleLinkModel.project_id == project_id,
                RuleLinkModel.target_kind == target_kind,
                RuleLinkModel.target_logical_uuid == target_logical_uuid,
            )
            .order_by(RuleLinkModel.id.asc())
        )
        stmt = self._apply_workspace_filter(stmt, RuleLinkModel, workspace_id)
        result = await session.execute(stmt)
        return result.scalars().all()
