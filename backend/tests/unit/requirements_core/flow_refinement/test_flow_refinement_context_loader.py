from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.modules.requirements_core.flow_refinement.application.context_loader import (
    FlowRefinementContext,
    compute_refinement_context_hash,
    load_flow_refinement_context,
)
from backend.database.model import ScenarioModel


def test_compute_refinement_context_hash_deterministic():
    steps1 = [
        {"position": 1, "name": "Step A", "step_type": "actorAction"},
        {"position": 2, "name": "Step B", "step_type": "systemAction"},
    ]
    steps2 = [
        {"position": 2, "name": "Step B", "step_type": "systemAction"},
        {"position": 1, "name": "Step A", "step_type": "actorAction"},
    ]
    transitions = [
        {"logical_uuid": "t-1", "source_step_position": 1, "target_step_position": 2, "condition_text": ""}
    ]
    rules = [
        {"logical_uuid": "r-1", "statement": "Rule 1", "parent_rule_uuid": None}
    ]
    scenarios = [
        {"logical_uuid": "sc-1", "name": "Scenario 1"}
    ]

    h1 = compute_refinement_context_hash("flow-uuid", "Flow 1", steps1, transitions, rules, scenarios)
    h2 = compute_refinement_context_hash("flow-uuid", "Flow 1", steps2, transitions, rules, scenarios)

    assert h1 == h2
    assert len(h1) == 64


def test_compute_refinement_context_hash_changes_on_mutation():
    base_steps = [{
        "position": 1,
        "name": "Step A",
        "step_type": "actorAction",
        "description": "Initial desc",
        "actor_ids": [1],
        "input_business_object_ids": [10],
        "output_business_object_ids": [20],
    }]
    base_trans = [{
        "logical_uuid": "t-1",
        "source_step_position": 1,
        "target_step_position": 2,
        "condition_text": "c1",
        "is_default": False,
        "semantic_tags": ["tag1"],
        "rule_refs": ["r-1"],
    }]
    base_rules = [{
        "logical_uuid": "r-1",
        "statement": "Rule 1",
        "confirmation_status": "ai_assumption",
        "origin": "manual",
        "source_links": [],
    }]
    base_scenarios = [{
        "logical_uuid": "sc-1",
        "name": "Scenario 1",
        "content": "Scenario body",
        "acceptance_criteria": "AC 1",
    }]
    base_features = [{"logical_uuid": "f-1", "name": "Feature 1"}]
    base_actors = [{"actor_id": 1, "name": "Admin"}]
    base_bos = [{"id": 10, "name": "Order"}]
    base_finding_context = "FC-01: Rule violation"

    h_base = compute_refinement_context_hash(
        "flow-uuid", "Flow 1", base_steps, base_trans, base_rules, base_scenarios,
        features=base_features, actors=base_actors, business_objects=base_bos,
        finding_context=base_finding_context, flow_description="Flow desc"
    )

    # 1. Flow description change
    h_desc = compute_refinement_context_hash(
        "flow-uuid", "Flow 1", base_steps, base_trans, base_rules, base_scenarios,
        features=base_features, actors=base_actors, business_objects=base_bos,
        finding_context=base_finding_context, flow_description="New desc"
    )
    assert h_base != h_desc

    # 2. Step description change
    mutated_steps = [dict(base_steps[0], description="Changed desc")]
    h_step_desc = compute_refinement_context_hash(
        "flow-uuid", "Flow 1", mutated_steps, base_trans, base_rules, base_scenarios,
        features=base_features, actors=base_actors, business_objects=base_bos,
        finding_context=base_finding_context, flow_description="Flow desc"
    )
    assert h_base != h_step_desc

    # 3. Step actor change
    mutated_steps_actor = [dict(base_steps[0], actor_ids=[2])]
    h_step_actor = compute_refinement_context_hash(
        "flow-uuid", "Flow 1", mutated_steps_actor, base_trans, base_rules, base_scenarios,
        features=base_features, actors=base_actors, business_objects=base_bos,
        finding_context=base_finding_context, flow_description="Flow desc"
    )
    assert h_base != h_step_actor

    # 4. Step BO change
    mutated_steps_bo = [dict(base_steps[0], input_business_object_ids=[99])]
    h_step_bo = compute_refinement_context_hash(
        "flow-uuid", "Flow 1", mutated_steps_bo, base_trans, base_rules, base_scenarios,
        features=base_features, actors=base_actors, business_objects=base_bos,
        finding_context=base_finding_context, flow_description="Flow desc"
    )
    assert h_base != h_step_bo

    # 5. Transition is_default change
    mutated_trans = [dict(base_trans[0], is_default=True)]
    h_trans = compute_refinement_context_hash(
        "flow-uuid", "Flow 1", base_steps, mutated_trans, base_rules, base_scenarios,
        features=base_features, actors=base_actors, business_objects=base_bos,
        finding_context=base_finding_context, flow_description="Flow desc"
    )
    assert h_base != h_trans

    # 6. Rule confirmation_status change
    mutated_rules = [dict(base_rules[0], confirmation_status="confirmed")]
    h_rule = compute_refinement_context_hash(
        "flow-uuid", "Flow 1", base_steps, base_trans, mutated_rules, base_scenarios,
        features=base_features, actors=base_actors, business_objects=base_bos,
        finding_context=base_finding_context, flow_description="Flow desc"
    )
    assert h_base != h_rule

    # 7. Scenario acceptance_criteria change
    mutated_scen = [dict(base_scenarios[0], acceptance_criteria="New AC")]
    h_scen = compute_refinement_context_hash(
        "flow-uuid", "Flow 1", base_steps, base_trans, base_rules, mutated_scen,
        features=base_features, actors=base_actors, business_objects=base_bos,
        finding_context=base_finding_context, flow_description="Flow desc"
    )
    assert h_base != h_scen

    # 8. Finding context change
    h_find = compute_refinement_context_hash(
        "flow-uuid", "Flow 1", base_steps, base_trans, base_rules, base_scenarios,
        features=base_features, actors=base_actors, business_objects=base_bos,
        finding_context="Different finding info", flow_description="Flow desc"
    )
    assert h_base != h_find


@pytest.mark.asyncio
async def test_load_flow_refinement_context_flow_not_found():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    with pytest.raises(ValueError) as excinfo:
        await load_flow_refinement_context(
            session=mock_session,
            project_id=1,
            target_kind="flow",
            target_id=999,
                  workspace_id=2,
        )
    assert "flow_not_found" in str(excinfo.value)


def test_compute_refinement_context_hash_changes_on_knowledge_mutation():
    """Verify knowledge fragments affect context hash."""
    h_no_k = compute_refinement_context_hash(
        "flow-uuid", "Flow 1", [], [], [], [],
        knowledge_fragments=[]
    )
    h_with_k = compute_refinement_context_hash(
        "flow-uuid", "Flow 1", [], [], [], [],
        knowledge_fragments=[{"uuid": "chunk-1", "content": "Knowledge content"}]
    )
    assert h_no_k != h_with_k


@pytest.mark.asyncio
async def test_load_flow_refinement_context_finding_not_found_fails_fast():
    """Verify missing source finding raises ValueError rather than returning dummy text."""
    mock_session = AsyncMock()
    # Mock flow exists
    mock_flow = MagicMock()
    mock_flow.id = 1
    mock_flow.logical_uuid = "flow-uuid"
    mock_flow.name = "Checkout Flow"
    mock_flow.description = "Checkout Flow description"

    def mock_execute(stmt, *args, **kwargs):
        res = MagicMock()
        stmt_str = str(stmt)
        if "flows" in stmt_str:
            res.scalar_one_or_none.return_value = mock_flow
        else:
            res.scalar_one_or_none.return_value = None
            res.scalars.return_value.all.return_value = []
        return res

    mock_session.execute.side_effect = mock_execute

    with patch(
        "backend.api.modules.requirements_core.flow_refinement.application.context_loader.HowFindingPolicy"
    ) as mock_policy_cls:
        mock_policy_inst = MagicMock()
        mock_policy_inst.get_findings = AsyncMock(return_value=[])  # No matching finding
        mock_policy_cls.return_value = mock_policy_inst

        with pytest.raises(ValueError) as excinfo:
            await load_flow_refinement_context(
                session=mock_session,
                project_id=1,
                target_kind="flow",
                target_id=1,
                source_finding_id="non-existent-finding-uuid",
                      workspace_id=2,
            )
        assert "finding_not_found: non-existent-finding-uuid" in str(excinfo.value)


@pytest.mark.asyncio
async def test_load_flow_refinement_context_finding_retrieval_failed_fails_fast():
    """Verify exception during finding retrieval raises ValueError rather than falling back."""
    mock_session = AsyncMock()
    mock_flow = MagicMock()
    mock_flow.id = 1
    mock_flow.logical_uuid = "flow-uuid"
    mock_flow.name = "Checkout Flow"
    mock_flow.description = "Checkout Flow description"

    def mock_execute(stmt, *args, **kwargs):
        res = MagicMock()
        stmt_str = str(stmt)
        if "flows" in stmt_str:
            res.scalar_one_or_none.return_value = mock_flow
        else:
            res.scalar_one_or_none.return_value = None
            res.scalars.return_value.all.return_value = []
        return res

    mock_session.execute.side_effect = mock_execute

    with patch(
        "backend.api.modules.requirements_core.flow_refinement.application.context_loader.HowFindingPolicy"
    ) as mock_policy_cls:
        mock_policy_inst = MagicMock()
        mock_policy_inst.get_findings = AsyncMock(side_effect=RuntimeError("finding DB index corrupt"))
        mock_policy_cls.return_value = mock_policy_inst

        with pytest.raises(ValueError) as excinfo:
            await load_flow_refinement_context(
                session=mock_session,
                project_id=1,
                target_kind="flow",
                target_id=1,
                source_finding_id="some-finding-uuid",
                      workspace_id=2,
            )
        assert "finding_retrieval_failed: some-finding-uuid" in str(excinfo.value)
        assert "finding DB index corrupt" in str(excinfo.value)


@pytest.mark.asyncio
async def test_load_flow_refinement_context_flow_level_scopes_actors_and_bos_to_flow_steps():
    """Verify Flow-level refinement confines allowed_actor_ids and allowed_bo_ids to target Flow's steps."""
    mock_session = AsyncMock()

    mock_flow = MagicMock()
    mock_flow.id = 1
    mock_flow.logical_uuid = "flow-uuid-1"
    mock_flow.name = "Order Flow"
    mock_flow.description = "Order Flow description"

    mock_feature = MagicMock()
    mock_feature.id = 301
    mock_feature.logical_uuid = "feature-uuid-1"
    mock_feature.name = "Place order"
    mock_feature.description = "Customer places an order"
    mock_flow.features = [mock_feature]

    mock_scenario = ScenarioModel(
        id=401,
        logical_uuid="scenario-uuid-1",
        project_id=1,
        feature_id=301,
        actor_id=101,
        name="Successful order",
        content="The customer successfully places an order",
        acceptance_criteria=[],
    )

    mock_actor1 = MagicMock()
    mock_actor1.id = 101
    mock_actor1.name = "Customer"
    mock_actor1.description = "Buyer"

    mock_actor2 = MagicMock()
    mock_actor2.id = 999
    mock_actor2.name = "Warehouse Manager"
    mock_actor2.description = "Only in Flow 2"

    mock_bo1 = MagicMock()
    mock_bo1.id = 201
    mock_bo1.number = "BO-FLOW-1"
    mock_bo1.name = "Order"
    mock_bo1.description = "Order BO"
    mock_bo1.attributes = []

    mock_bo2 = MagicMock()
    mock_bo2.id = 999
    mock_bo2.number = "BO-FLOW-2"
    mock_bo2.name = "Shipment"
    mock_bo2.description = "Only in Flow 2"
    mock_bo2.attributes = []

    mock_step1 = MagicMock()
    mock_step1.id = 10
    mock_step1.flow_id = 1
    mock_step1.position = 1
    mock_step1.logical_uuid = "step-uuid-1"
    mock_step1.name = "Place Order"
    mock_step1.description = "Customer places order"
    mock_step1.step_type = "actorAction"
    mock_step1.confirmation_status = "ai_assumption"
    mock_step1.actors = [mock_actor1]
    mock_step1.input_business_objects = [mock_bo1]
    mock_step1.output_business_objects = []

    def mock_execute(stmt, *args, **kwargs):
        res = MagicMock()
        stmt_str = str(stmt)
        if "flows" in stmt_str and "flow_steps" not in stmt_str and "flow_transitions" not in stmt_str:
            res.scalar_one_or_none.return_value = mock_flow
        elif "flow_steps" in stmt_str:
            res.scalars.return_value.all.return_value = [mock_step1]
        elif "flow_transitions" in stmt_str:
            res.scalars.return_value.all.return_value = []
        elif "actors" in stmt_str:
            res.scalars.return_value.all.return_value = [mock_actor1, mock_actor2]
        elif "business_objects" in stmt_str:
            res.scalars.return_value.all.return_value = [mock_bo1, mock_bo2]
        elif "scenarios" in stmt_str:
            res.scalars.return_value.all.return_value = [mock_scenario]
        else:
            res.scalars.return_value.all.return_value = []
            res.scalar_one_or_none.return_value = None
        return res

    mock_session.execute.side_effect = mock_execute

    with patch(
        "backend.services.knowledge.retrieval.KnowledgeRetrievalService.retrieve_chunks",
        new=AsyncMock(return_value=[]),
    ) as retrieve_chunks:
        ctx = await load_flow_refinement_context(
            session=mock_session,
            project_id=1,
            target_kind="flow",
            target_id=1,
            workspace_id=2,
        )

        assert retrieve_chunks.await_args.kwargs["project_id"] == 1
        assert "workspace_id" not in retrieve_chunks.await_args.kwargs

        # Verified: Actors and BOs are strictly scoped to Flow 1's steps
        assert ctx.allowed_actor_ids == {101}
        assert 999 not in ctx.allowed_actor_ids

        assert ctx.allowed_bo_ids == {201}
        assert 999 not in ctx.allowed_bo_ids

        assert ctx.allowed_bo_numbers == {"BO-201"}
        assert "BO-999" not in ctx.allowed_bo_numbers

        assert [a["id"] for a in ctx.actors] == [101]
        assert [b["id"] for b in ctx.business_objects] == [201]
        assert ctx.linked_requirements["scenarios"] == [{
            "scenario_id": 401,
            "logical_uuid": "scenario-uuid-1",
            "name": "Successful order",
            "content": "The customer successfully places an order",
            "acceptance_criteria": [],
        }]
