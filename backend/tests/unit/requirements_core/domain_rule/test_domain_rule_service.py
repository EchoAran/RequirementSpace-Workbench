"""Unit tests for DomainRuleService lifecycle, invariants, and linking."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.modules.requirements_core.domain_rule.application.domain_rule_service import (
    DomainRuleService,
)
from backend.api.modules.requirements_core.domain_rule.domain.node_resolver import (
    RequirementNodeResolver,
)
from backend.api.modules.requirements_core.domain_rule.schemas import (
    DomainRuleCreateRequest,
    DomainRuleUpdateRequest,
    RuleLinkCreateRequest,
)
from backend.database.database import Base
from backend.database.model import (
    ConfirmationStatus,
    BranchWorkspaceModel,
    RequirementBranchModel,
    DomainRuleModel,
    FeatureModel,
    FlowModel,
    FlowStepModel,
    ProjectModel,
    RuleLinkModel,
    ScenarioAcceptanceCriterionModel,
    ScenarioModel,
)


@pytest_asyncio.fixture
async def session_factory():
    """Create in-memory SQLite database."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def test_project(session_factory) -> int:
    async with session_factory() as session:
        project = ProjectModel(name="Rule Test Project", owner_user_id=1)
        session.add(project)
        await session.flush()
        branch = RequirementBranchModel(project_id=project.id, name="main")
        session.add(branch)
        await session.flush()
        workspace = BranchWorkspaceModel(project_id=project.id, branch_id=branch.id)
        session.add(workspace)
        await session.commit()
        return project.id, workspace.id


@pytest.mark.asyncio
async def test_create_rule_manual_defaults(session_factory, test_project):
    """Test creating a manual rule defaults confirmation_status to needs_confirmation."""
    project_id, workspace_id = test_project
    service = DomainRuleService()
    async with session_factory() as session:
        rule = await service.create_rule(
            session=session,
            project_id=project_id,
            request=DomainRuleCreateRequest(
                title="Unique SKU Rule",
                statement="SKU must be globally unique across active product catalog.",
                origin="manual",
            ),
                         workspace_id=workspace_id,
        )
        await session.commit()

        assert rule.id is not None
        assert rule.title == "Unique SKU Rule"
        assert rule.statement == "SKU must be globally unique across active product catalog."
        assert rule.origin == "manual"
        assert rule.confirmation_status == ConfirmationStatus.NEEDS_CONFIRMATION.value


@pytest.mark.asyncio
async def test_update_rule_confirmed_resets_on_text_change(session_factory, test_project):
    """Test editing title/statement of a confirmed rule resets confirmation status to needs_confirmation."""
    project_id, workspace_id = test_project
    service = DomainRuleService()
    async with session_factory() as session:
        rule = await service.create_rule(
            session=session,
            project_id=project_id,
            request=DomainRuleCreateRequest(
                title="Stock Threshold",
                statement="Safety stock threshold is 10 units.",
                origin="manual",
            ),
                         workspace_id=workspace_id,
        )
        rule.confirmation_status = ConfirmationStatus.CONFIRMED.value
        await session.commit()

        # Update title only
        updated = await service.update_rule(
            session=session,
            project_id=project_id,
            rule_id=rule.id,
            request=DomainRuleUpdateRequest(statement="Safety stock threshold is 20 units."),
                            workspace_id=workspace_id,
        )
        await session.commit()

        assert updated.statement == "Safety stock threshold is 20 units."
        assert updated.confirmation_status == ConfirmationStatus.NEEDS_CONFIRMATION.value


@pytest.mark.asyncio
async def test_parent_hierarchy_cycle_detection(session_factory, test_project):
    """Test cycle detection prevents a rule from setting its descendant or self as parent."""
    project_id, workspace_id = test_project
    service = DomainRuleService()
    async with session_factory() as session:
        # Rule 1
        r1 = await service.create_rule(
            session=session,
            project_id=project_id,
            request=DomainRuleCreateRequest(title="R1", statement="Base rule"),
                       workspace_id=workspace_id,
        )
        # Rule 2 child of R1
        r2 = await service.create_rule(
            session=session,
            project_id=project_id,
            request=DomainRuleCreateRequest(title="R2", statement="Child of R1", parent_rule_id=r1.id),
                       workspace_id=workspace_id,
        )
        # Rule 3 child of R2
        r3 = await service.create_rule(
            session=session,
            project_id=project_id,
            request=DomainRuleCreateRequest(title="R3", statement="Child of R2", parent_rule_id=r2.id),
                       workspace_id=workspace_id,
        )
        await session.commit()

        # Self-parent attempt
        with pytest.raises(ValueError, match="cannot be its own parent"):
            await service.update_rule(
                session=session,
                project_id=project_id,
                rule_id=r1.id,
                request=DomainRuleUpdateRequest(parent_rule_id=r1.id),
                      workspace_id=workspace_id,
            )

        # Cyclic attempt: setting R3 as parent of R1 (creates cycle R1 -> R3 -> R2 -> R1)
        with pytest.raises(ValueError, match="Cyclic parent hierarchy detected"):
            await service.update_rule(
                session=session,
                project_id=project_id,
                rule_id=r1.id,
                request=DomainRuleUpdateRequest(parent_rule_id=r3.id),
                      workspace_id=workspace_id,
            )


@pytest.mark.asyncio
async def test_rule_link_target_resolution_and_duplicates(session_factory, test_project):
    """Test linking rule to existing targets and rejecting non-existent targets or duplicates."""
    project_id, workspace_id = test_project
    service = DomainRuleService()
    async with session_factory() as session:
        # Create Feature
        feat = FeatureModel(project_id=project_id, name="Checkout", description="Cart checkout", workspace_id=workspace_id)
        session.add(feat)
        await session.flush()

        # Create Rule
        rule = await service.create_rule(
            session=session,
            project_id=project_id,
            request=DomainRuleCreateRequest(title="Payment Rule", statement="Card must be valid"),
                         workspace_id=workspace_id,
        )
        await session.commit()

        # Valid link to feature
        link = await service.create_link(
            session=session,
            project_id=project_id,
            rule_id=rule.id,
            request=RuleLinkCreateRequest(
                target_kind="feature",
                target_logical_uuid=feat.logical_uuid,
                link_purpose="applies_to",
            ),
                         workspace_id=workspace_id,
        )
        await session.commit()
        assert link.id is not None
        assert link.target_logical_uuid == feat.logical_uuid

        # Duplicate link attempt
        with pytest.raises(ValueError, match="Rule link already exists"):
            await service.create_link(
                session=session,
                project_id=project_id,
                rule_id=rule.id,
                request=RuleLinkCreateRequest(
                    target_kind="feature",
                    target_logical_uuid=feat.logical_uuid,
                    link_purpose="applies_to",
                ),
                      workspace_id=workspace_id,
            )

        # Invalid target UUID
        with pytest.raises(ValueError, match="not found"):
            await service.create_link(
                session=session,
                project_id=project_id,
                rule_id=rule.id,
                request=RuleLinkCreateRequest(
                    target_kind="feature",
                    target_logical_uuid="non-existent-uuid-1234",
                    link_purpose="applies_to",
                ),
                      workspace_id=workspace_id,
            )

        # Unsupported target kind
        with pytest.raises(ValueError, match="Unsupported target kind"):
            await service.create_link(
                session=session,
                project_id=project_id,
                rule_id=rule.id,
                request=RuleLinkCreateRequest(
                    target_kind="unsupported_target",
                    target_logical_uuid="some-uuid",
                    link_purpose="applies_to",
                ),
                      workspace_id=workspace_id,
            )


@pytest.mark.asyncio
async def test_delete_rule_cascades_links_and_unbinds_children(session_factory, test_project):
    """Test deleting rule cascades links and sets child rules' parent_rule_id to null."""
    project_id, workspace_id = test_project
    service = DomainRuleService()
    async with session_factory() as session:
        feat = FeatureModel(project_id=project_id, name="Inventory", description="Inv", workspace_id=workspace_id)
        session.add(feat)
        await session.flush()

        parent_rule = await service.create_rule(
            session=session,
            project_id=project_id,
            request=DomainRuleCreateRequest(title="Parent Rule", statement="Parent"),
                                workspace_id=workspace_id,
        )
        child_rule = await service.create_rule(
            session=session,
            project_id=project_id,
            request=DomainRuleCreateRequest(title="Child Rule", statement="Child", parent_rule_id=parent_rule.id),
                               workspace_id=workspace_id,
        )
        link = await service.create_link(
            session=session,
            project_id=project_id,
            rule_id=parent_rule.id,
            request=RuleLinkCreateRequest(target_kind="feature", target_logical_uuid=feat.logical_uuid),
                         workspace_id=workspace_id,
        )
        await session.commit()

        # Delete parent
        success = await service.delete_rule(session=session, project_id=project_id, rule_id=parent_rule.id, workspace_id=workspace_id)
        await session.commit()
        assert success is True

        # Verify child rule has parent_rule_id set to None
        refreshed_child = await service.get_rule(session, project_id, child_rule.id, workspace_id=workspace_id)
        assert refreshed_child is not None
        assert refreshed_child.parent_rule_id is None


@pytest.mark.asyncio
async def test_domain_rule_notifier_failure_propagates_exception(session_factory, test_project):
    """Notifier failure must raise an exception instead of being silently swallowed."""
    project_id, workspace_id = test_project
    from backend.core.notifier import get_notifier, set_notifier

    class CrashingNotifier:
        async def mark_stale(self, *args, **kwargs):
            raise RuntimeError("Perception notification channel failure!")

    original_notifier = get_notifier()
    set_notifier(CrashingNotifier())
    service = DomainRuleService()

    try:
        async with session_factory() as session:
            with pytest.raises(RuntimeError, match="Perception notification channel failure!"):
                await service.create_rule(
                    session=session,
                    project_id=project_id,
                    request=DomainRuleCreateRequest(title="Failing Notifier Rule", statement="Statement text"),
                          workspace_id=workspace_id,
                )
    finally:
        set_notifier(original_notifier)


import json
from fastapi import HTTPException
from backend.api.modules.version_control.application.workspace_serializer import (
    serialize_workspace,
)
from backend.api.modules.version_control.public import compute_state_hash
from backend.database.model import (
    ActorModel,
    BranchWorkspaceModel,
    RequirementBranchModel,
)


@pytest.mark.asyncio
async def test_domain_rule_optimistic_locking_conflict(session_factory, test_project):
    """Updating a rule with stale last_seen_updated_at must raise HTTPException 409."""
    project_id, workspace_id = test_project
    service = DomainRuleService()
    async with session_factory() as session:
        rule = await service.create_rule(
            session=session,
            project_id=project_id,
            request=DomainRuleCreateRequest(title="Concurrency Target", statement="Initial text"),
                         workspace_id=workspace_id,
        )
        await session.commit()

        # Update with outdated last_seen_updated_at (e.g. 2020-01-01)
        with pytest.raises(HTTPException) as exc_info:
            await service.update_rule(
                session=session,
                project_id=project_id,
                rule_id=rule.id,
                request=DomainRuleUpdateRequest(
                    title="Changed Title",
                    last_seen_updated_at="2020-01-01T00:00:00Z",
                ),
                      workspace_id=workspace_id,
            )
        assert exc_info.value.status_code == 409
        assert exc_info.value.detail.get("message") == "node_content_changed"


@pytest.mark.asyncio
async def test_domain_rule_cross_workspace_isolation(session_factory, test_project):
    """Rules created in main workspace vs branch workspaces must be completely isolated."""
    project_id, workspace_id = test_project
    service = DomainRuleService()
    async with session_factory() as session:
        # Create a branch workspace entity
        branch = RequirementBranchModel(project_id=project_id, name="branch-iso")
        session.add(branch)
        await session.flush()
        ws = BranchWorkspaceModel(project_id=project_id, branch_id=branch.id)
        session.add(ws)
        await session.flush()

        # Create main workspace rule
        main_rule = await service.create_rule(
            session=session,
            project_id=project_id,
            request=DomainRuleCreateRequest(title="Main Workspace Rule", statement="Statement Main"),
            workspace_id=workspace_id,
        )

        # Create branch workspace rule
        branch_rule = await service.create_rule(
            session=session,
            project_id=project_id,
            request=DomainRuleCreateRequest(title="Branch Workspace Rule", statement="Statement Branch"),
            workspace_id=ws.id,
        )
        await session.commit()

        # Listing main workspace returns only main rule
        main_rules, main_count = await service.list_rules(session=session, project_id=project_id, workspace_id=workspace_id)
        assert main_count == 1
        assert len(main_rules) == 1
        assert main_rules[0].id == main_rule.id
        assert main_rules[0].workspace_id == workspace_id

        # Listing branch workspace returns only branch rule
        branch_rules, branch_count = await service.list_rules(session=session, project_id=project_id, workspace_id=ws.id)
        assert branch_count == 1
        assert len(branch_rules) == 1
        assert branch_rules[0].id == branch_rule.id
        assert branch_rules[0].workspace_id == ws.id


@pytest.mark.asyncio
async def test_domain_rule_parent_cross_project_and_workspace_rejection(session_factory, test_project):
    """Parent rule cannot belong to another project or another workspace."""
    project_id, workspace_id = test_project
    service = DomainRuleService()
    async with session_factory() as session:
        # Create Project 2
        p2 = ProjectModel(name="Project 2", owner_user_id=1)
        session.add(p2)
        await session.flush()

        # Create a branch workspace in test_project
        branch = RequirementBranchModel(project_id=project_id, name="branch-cross-ws")
        session.add(branch)
        await session.flush()
        ws = BranchWorkspaceModel(project_id=project_id, branch_id=branch.id)
        session.add(ws)
        await session.flush()

        # Rule in test_project, main workspace
        rule_p1 = await service.create_rule(
            session=session,
            project_id=project_id,
            request=DomainRuleCreateRequest(title="P1 Rule", statement="P1 Statement"),
            workspace_id=workspace_id,
        )
        await session.commit()

        # Attempt to create rule in p2 referencing rule_p1 -> rejected
        with pytest.raises(ValueError, match="does not exist in workspace"):
            await service.create_rule(
                session=session,
                project_id=p2.id,
                request=DomainRuleCreateRequest(
                    title="P2 Child Rule",
                    statement="Invalid cross project parent",
                    parent_rule_id=rule_p1.id,
                ),
                workspace_id=workspace_id,
            )

        # Attempt to create rule in test_project branch referencing rule_p1 (main workspace) -> rejected
        with pytest.raises(ValueError, match="does not exist in workspace"):
            await service.create_rule(
                session=session,
                project_id=project_id,
                request=DomainRuleCreateRequest(
                    title="Branch Child Rule",
                    statement="Invalid cross workspace parent",
                    parent_rule_id=rule_p1.id,
                ),
                workspace_id=ws.id,
            )


@pytest.mark.asyncio
async def test_domain_rule_target_deletion_cascade_cleans_rule_links(session_factory, test_project):
    """Deleting linked targets via real services (Feature, Scenario, AC) must cascade and clean orphaned RuleLinks."""
    project_id, workspace_id = test_project
    service = DomainRuleService()
    async with session_factory() as session:
        # Create target entities
        feat = FeatureModel(project_id=project_id, name="Cascade Feature", description="desc", confirmation_status="confirmed", workspace_id=workspace_id)
        session.add(feat)
        await session.flush()

        actor = ActorModel(project_id=project_id, name="Cascade Actor", description="desc", confirmation_status="confirmed", workspace_id=workspace_id)
        session.add(actor)
        await session.flush()

        scen = ScenarioModel(project_id=project_id, feature_id=feat.id, actor_id=actor.id, name="Cascade Scenario", content="content", confirmation_status="confirmed", workspace_id=workspace_id)
        session.add(scen)
        await session.flush()

        ac = ScenarioAcceptanceCriterionModel(scenario_id=scen.id, content="Cascade AC", position=1, confirmation_status="confirmed", workspace_id=workspace_id)
        session.add(ac)
        await session.flush()

        rule = await service.create_rule(
            session=session,
            project_id=project_id,
            request=DomainRuleCreateRequest(title="Target Deletion Rule", statement="Statement"),
                         workspace_id=workspace_id,
        )
        await session.flush()

        # Create links to feat, scen, and ac
        await service.create_link(session, project_id, rule.id, RuleLinkCreateRequest(target_kind="feature", target_logical_uuid=feat.logical_uuid), workspace_id=workspace_id)
        await service.create_link(session, project_id, rule.id, RuleLinkCreateRequest(target_kind="scenario", target_logical_uuid=scen.logical_uuid), workspace_id=workspace_id)
        await service.create_link(session, project_id, rule.id, RuleLinkCreateRequest(target_kind="acceptance_criterion", target_logical_uuid=ac.logical_uuid), workspace_id=workspace_id)
        await session.commit()

        # Verify all 3 links exist
        rule_detail = await service.get_rule(session, project_id, rule.id, workspace_id=workspace_id)
        assert len(rule_detail.links) == 3

        from backend.api.modules.requirements_core.scenario.application.scenario_service import (
            ScenarioService,
        )
        from backend.api.modules.requirements_core.feature.application.feature_service import (
            FeatureService,
        )

        scen_svc = ScenarioService()
        feat_svc = FeatureService()

        # 1. Delete AC via real ScenarioService deletion API
        await scen_svc.delete_acceptance_criterion(
            project_id=project_id,
            scenario_id=scen.id,
            ac_id=ac.id,
            session=session,
                  workspace_id=workspace_id,
        )
        await session.flush()
        rule_detail = await service.get_rule(session, project_id, rule.id, workspace_id=workspace_id)
        assert len(rule_detail.links) == 2
        assert all(l.target_kind != "acceptance_criterion" for l in rule_detail.links)

        # 2. Delete Scenario via real ScenarioService deletion API
        await scen_svc.delete_scenario(
            project_id=project_id,
            scenario_id=scen.id,
            session=session,
                  workspace_id=workspace_id,
        )
        await session.flush()
        rule_detail = await service.get_rule(session, project_id, rule.id, workspace_id=workspace_id)
        assert len(rule_detail.links) == 1
        assert rule_detail.links[0].target_kind == "feature"

        # 3. Delete Feature via real FeatureService deletion API
        await feat_svc.delete_feature(
            project_id=project_id,
            feature_id=feat.id,
            session=session,
                  workspace_id=workspace_id,
        )
        await session.flush()
        rule_detail = await service.get_rule(session, project_id, rule.id, workspace_id=workspace_id)
        assert len(rule_detail.links) == 0


@pytest.mark.asyncio
async def test_domain_rule_changes_impact_workspace_hash(session_factory, test_project):
    """Creating, updating, and deleting domain rules in a branch workspace must alter serialized state and workspace hash."""
    project_id, workspace_id = test_project
    service = DomainRuleService()
    async with session_factory() as session:
        branch = RequirementBranchModel(project_id=project_id, name="feature-rules")
        session.add(branch)
        await session.flush()
        ws = BranchWorkspaceModel(
            project_id=project_id,
            branch_id=branch.id,
            user_requirements="Base requirements",
        )
        session.add(ws)
        await session.commit()
        await session.refresh(ws)

        # 1. Base workspace hash with no rules
        base_state = await session.run_sync(lambda s: serialize_workspace(s, ws))
        base_hash = compute_state_hash(json.dumps(base_state, sort_keys=True))
        assert base_state.get("domain_rules") == []

        # 2. Add domain rule to workspace
        rule = await service.create_rule(
            session=session,
            project_id=project_id,
            request=DomainRuleCreateRequest(title="State Hash Rule 1", statement="Rule statement 1"),
            workspace_id=ws.id,
        )
        await session.commit()

        state_after_create = await session.run_sync(lambda s: serialize_workspace(s, ws))
        hash_after_create = compute_state_hash(json.dumps(state_after_create, sort_keys=True))
        assert len(state_after_create.get("domain_rules", [])) == 1
        assert hash_after_create != base_hash

        # 3. Update domain rule title/statement
        await service.update_rule(
            session=session,
            project_id=project_id,
            rule_id=rule.id,
            request=DomainRuleUpdateRequest(title="State Hash Rule 1 Modified"),
            workspace_id=ws.id,
        )
        await session.commit()

        state_after_update = await session.run_sync(lambda s: serialize_workspace(s, ws))
        hash_after_update = compute_state_hash(json.dumps(state_after_update, sort_keys=True))
        assert hash_after_update != hash_after_create
        assert hash_after_update != base_hash

        # 4. Delete domain rule
        await service.delete_rule(
            session=session,
            project_id=project_id,
            rule_id=rule.id,
            workspace_id=ws.id,
        )
        await session.commit()

        state_after_delete = await session.run_sync(lambda s: serialize_workspace(s, ws))
        hash_after_delete = compute_state_hash(json.dumps(state_after_delete, sort_keys=True))
        assert len(state_after_delete.get("domain_rules", [])) == 0
        assert hash_after_delete != hash_after_update
        assert hash_after_delete == base_hash
