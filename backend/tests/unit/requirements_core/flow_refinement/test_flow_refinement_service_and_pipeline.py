from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.modules.requirements_core.flow_refinement.application.context_loader import FlowRefinementContext

from backend.api.modules.requirements_core.flow_refinement.application.flow_refinement_service import (
    FlowRefinementService,
)


def _make_sample_context():
    return FlowRefinementContext(
        project_id=1,
        workspace_id=2,
        target_flow_id=10,
        target_flow_logical_uuid="flow-uuid-10",
        target_flow_name="Order Process",
        target_flow_description="Initial flow",
        anchor_kind="flow",
        anchor_id=10,
        anchor_step={"position": 1, "name": "Submit Order"},
        existing_steps=[
            {"position": 1, "logical_uuid": "step-uuid-1", "name": "Submit Order"},
            {"position": 2, "logical_uuid": "step-uuid-2", "name": "Complete Order"},
        ],
        existing_transitions=[
            {"logical_uuid": "trans-uuid-1", "source_step_position": 1, "target_step_position": 2, "condition_text": ""}
        ],
        path_projection={},
        linked_requirements={},
        applicable_rules=[{"logical_uuid": "rule-1", "statement": "Parent rule", "id": 55}],
        business_objects=[],
        actors=[],
        allowed_step_positions=None,
        allowed_step_uuids=None,
        allowed_transition_uuids=None,
        allowed_actor_ids=set(),
        allowed_bo_ids=set(),
        allowed_bo_numbers=set(),
        context_feature_uuids={"feat-1"},
        context_hash="server_authoritative_hash_999",
    )

@pytest.mark.asyncio
async def test_generate_raw_success():
    mock_generator = AsyncMock()
    mock_generator.generate.return_value = {
        "summary": "Added inventory check step and business rule",
        "rationale": "Reasoning",
        "steps_added": [
            {
                "temp_id": "temp_step_1",
                "name": "Check Inventory",
                "description": "Verify stock availability",
                "step_type": "systemAction",
            }
        ],
        "transitions_added": [
            {
                "temp_id": "temp_trans_1",
                "source_step_ref": 1,
                "target_step_ref": "temp_step_1",
                "label": "Has stock",
                "condition_text": "stock_available",
                "is_default": True,
            }
        ],
        "transitions_updated": [
            {
                "logical_uuid": "trans-uuid-1",
                "label": "rerouted",
                "condition_text": "re-routed",
            }
        ],
        "rules_added": [
            {
                "temp_id": "temp_rule_1",
                "statement": "Stock locked for 10 minutes",
                "name": "Inventory Reservation Rule",
                "description": "Stock locked for 10 minutes",
                "parent_rule_ref": "rule-1",
            }
        ],
        "rule_links_added": [
            {
                "rule_ref": "temp_rule_1",
                "target_kind": "flow_step",
                "target_ref": "temp_step_1",
            }
        ],
        "business_objects_added": [],
    }

    service = FlowRefinementService(generator=mock_generator)
    mock_session = AsyncMock()
    mock_session.begin_nested = MagicMock(return_value=AsyncMock())

    with patch(
        "backend.api.modules.requirements_core.flow_refinement.application.flow_refinement_service.load_flow_refinement_context"
    ) as mock_load:
        mock_load.return_value = _make_sample_context()

        payload, ctx = await service.generate_raw(
            session=mock_session,
            project_id=1,
            target_kind="flow",
            target_id=10,
            user_feedback="Add inventory check",
                                 workspace_id=2,
        )

        assert ctx.context_hash == "server_authoritative_hash_999"
        assert len(payload["steps_added"]) == 1
        assert payload["steps_added"][0]["name"] == "Check Inventory"
        assert len(payload["transitions_added"]) == 1
        assert len(payload["rules_added"]) == 1
        mock_generator.generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_raw_fails_on_bounds_exceeded():
    mock_generator = AsyncMock()
    # 6 steps > MAX_ADDED_STEPS (5)
    mock_generator.generate.return_value = {
        "summary": "Too many steps",
        "rationale": "Over limit",
        "steps_added": [
            {
                "temp_id": f"temp_step_{i}",
                "name": f"Step {i}",
                "description": "",
                "step_type": "systemAction",
            }
            for i in range(6)
        ],
        "transitions_added": [],
        "transitions_updated": [],
        "rules_added": [],
        "rule_links_added": [],
        "business_objects_added": [],
    }

    service = FlowRefinementService(generator=mock_generator)
    mock_session = AsyncMock()
    mock_session.begin_nested = MagicMock(return_value=AsyncMock())

    with patch(
        "backend.api.modules.requirements_core.flow_refinement.application.flow_refinement_service.load_flow_refinement_context"
    ) as mock_load:
        mock_load.return_value = _make_sample_context()

        with pytest.raises(ValueError) as excinfo:
            await service.generate_raw(
                session=mock_session,
                project_id=1,
                target_kind="flow",
                target_id=10,
                      workspace_id=2,
            )
        assert "refinement_step_limit_exceeded" in str(excinfo.value)


@pytest.mark.asyncio
async def test_apply_refinement_persists_entities():
    mock_policy = MagicMock()
    mock_policy.get_findings = AsyncMock(return_value=[])
    service = FlowRefinementService(generator=MagicMock(), finding_policy=mock_policy)
    mock_session = AsyncMock()
    mock_session.begin_nested = MagicMock(return_value=AsyncMock())

    # Mock count query for position calculation and actor resolution
    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 2
    mock_count_result.scalar_one_or_none.return_value = 55
    mock_session.execute.return_value = mock_count_result
    mock_session.add = MagicMock()

    _id_counter = 100
    async def _mock_flush():
        nonlocal _id_counter
        for call in mock_session.add.call_args_list:
            obj = call[0][0]
            if getattr(obj, "id", None) is None:
                obj.id = _id_counter
                _id_counter += 1

    mock_session.flush.side_effect = _mock_flush

    payload = {
        "workspace_id": 2,
        "expected_workspace_version": "hash_val",
        "project_id": 1,
        "target_flow_id": 10,
        "context_hash": "hash_val",
        "steps_added": [
            {
                "temp_id": "temp_step_1",
                "name": "Check Inventory",
                "description": "Verify stock",
                "step_type": "systemAction",
                "actor_ids": [1],
                "input_business_object_numbers": ["BO-1"],
            }
        ],
        "transitions_added": [
            {
                "temp_id": "temp_trans_1",
                "source_step_ref": 1,
                "target_step_ref": "temp_step_1",
                "condition_text": "stock_ok",
                "label": "Proceed",
                "is_default": True,
            }
        ],
        "transitions_updated": [],
        "rules_added": [
            {
                "temp_id": "temp_rule_1",
                "statement": "Must reserve stock",
                "name": "Inventory Rule",
                "description": "Must reserve stock",
                "parent_rule_ref": "rule-1",
            }
        ],
        "rule_links_added": [
            {
                "rule_ref": "temp_rule_1",
                "target_kind": "flow_step",
                "target_ref": "temp_step_1",
                "role_description": "Link desc",
            }
        ],
        "business_objects_added": [],
    }

    with patch(
        "backend.api.modules.requirements_core.flow_refinement.application.flow_refinement_service.load_flow_refinement_context"
    ) as mock_load_ctx:
        mock_ctx = _make_sample_context()
        mock_ctx.context_hash = "hash_val"
        mock_ctx.existing_steps = [{"position": 1, "step_id": 101, "logical_uuid": "step-1"}]
        mock_ctx.business_objects = [{"number": "BO-1", "id": 2}]
        mock_ctx.allowed_actor_ids = {1}
        mock_ctx.allowed_bo_ids = {2}
        mock_load_ctx.return_value = mock_ctx

        result = await service.apply_refinement(
            payload=payload,
            session=mock_session,
                           workspace_id=2,
        )

        assert result["flow_id"] == 10
        assert result["steps_added_count"] == 1
        assert result["rules_added_count"] == 1
        assert result["transitions_added_count"] == 1
        assert mock_session.add.call_count >= 3  # Step, Rule, Transition, RuleLink
        assert mock_session.flush.call_count >= 3


@pytest.mark.asyncio
async def test_apply_refinement_rejects_disconnected_graph():
    mock_policy = MagicMock()
    mock_policy.get_findings = AsyncMock(return_value=[])
    service = FlowRefinementService(generator=MagicMock(), finding_policy=mock_policy)
    mock_session = AsyncMock()
    mock_session.begin_nested = MagicMock(return_value=AsyncMock())

    step1 = MagicMock(id=101)
    step2 = MagicMock(id=102)

    def mock_execute(stmt, *args, **kwargs):
        res = MagicMock()
        stmt_str = str(stmt)
        if "flow_step" in stmt_str:
            res.scalars.return_value.all.return_value = [step1, step2]
            res.scalar.return_value = 2
        elif "flow_transition" in stmt_str:
            res.scalars.return_value.all.return_value = []
        else:
            res.scalar.return_value = 2
            res.scalar_one_or_none.return_value = None
            res.scalars.return_value.all.return_value = []
        return res

    mock_session.execute.side_effect = mock_execute
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    payload = {
        "workspace_id": 2,
        "expected_workspace_version": "hash_val",
        "project_id": 1,
        "target_flow_id": 10,
        "context_hash": "hash_val",
        "steps_added": [],
        "transitions_added": [],
        "transitions_updated": [],
        "rules_added": [],
        "rule_links_added": [],
        "business_objects_added": [],
    }

    with patch(
        "backend.api.modules.requirements_core.flow_refinement.application.flow_refinement_service.load_flow_refinement_context"
    ) as mock_load_ctx:
        mock_ctx = _make_sample_context()
        mock_ctx.context_hash = "hash_val"
        mock_ctx.existing_steps = []
        mock_ctx.business_objects = []
        mock_load_ctx.return_value = mock_ctx

        with pytest.raises(ValueError) as excinfo:
            await service.apply_refinement(
                payload=payload,
                session=mock_session,
                      workspace_id=2,
            )
        assert "refinement_produced_disconnected_graph" in str(excinfo.value)


@pytest.mark.asyncio
async def test_apply_refinement_batch_temp_parent_rule_resolved():
    mock_policy = MagicMock()
    mock_policy.get_findings = AsyncMock(return_value=[])
    service = FlowRefinementService(generator=MagicMock(), finding_policy=mock_policy)
    mock_session = AsyncMock()
    mock_session.begin_nested = MagicMock(return_value=AsyncMock())

    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 1
    mock_count_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_count_result
    mock_session.add = MagicMock()

    _id_counter = 500
    added_rules = []
    async def _mock_flush():
        nonlocal _id_counter
        for call in mock_session.add.call_args_list:
            obj = call[0][0]
            if getattr(obj, "id", None) is None:
                obj.id = _id_counter
                _id_counter += 1
            from backend.database.model import DomainRuleModel
            if isinstance(obj, DomainRuleModel) and obj not in added_rules:
                added_rules.append(obj)

    mock_session.flush.side_effect = _mock_flush

    payload = {
        "workspace_id": 2,
        "expected_workspace_version": "hash_val",
        "project_id": 1,
        "target_flow_id": 10,
        "context_hash": "hash_val",
        "steps_added": [],
        "transitions_added": [],
        "transitions_updated": [],
        "rules_added": [
            {
                "temp_id": "temp_parent_rule",
                "statement": "Parent batch rule",
                "name": "Parent Batch Rule",
                "source_links": [{"target_kind": "feature", "target_ref": "feat-1"}],
            },
            {
                "temp_id": "temp_child_rule",
                "statement": "Child batch rule",
                "name": "Child Batch Rule",
                "parent_rule_ref": "temp_parent_rule",
            },
        ],
        "rule_links_added": [],
        "business_objects_added": [],
    }

    with patch(
        "backend.api.modules.requirements_core.flow_refinement.application.flow_refinement_service.load_flow_refinement_context"
    ) as mock_load_ctx:
        mock_ctx = _make_sample_context()
        mock_ctx.context_hash = "hash_val"
        mock_ctx.existing_steps = []
        mock_ctx.business_objects = []
        mock_load_ctx.return_value = mock_ctx

        result = await service.apply_refinement(
            payload=payload,
            session=mock_session,
                           workspace_id=2,
        )

        assert result["rules_added_count"] == 2
        # Check parent rule id assignment
        child_rule = next(r for r in added_rules if r.statement == "Child batch rule")
        parent_rule = next(r for r in added_rules if r.statement == "Parent batch rule")
        assert child_rule.parent_rule_id == parent_rule.id
        assert child_rule.origin == "flow_refinement"
        assert child_rule.confirmation_status == "ai_assumption"


@pytest.mark.asyncio
async def test_apply_refinement_child_before_parent_rule_resolved():
    """Verify order-independent parent rule resolution when child appears before parent."""
    mock_policy = MagicMock()
    mock_policy.get_findings = AsyncMock(return_value=[])
    service = FlowRefinementService(generator=MagicMock(), finding_policy=mock_policy)
    mock_session = AsyncMock()
    mock_session.begin_nested = MagicMock(return_value=AsyncMock())

    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 1
    mock_count_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_count_result
    mock_session.add = MagicMock()

    _id_counter = 800
    added_rules = []
    async def _mock_flush():
        nonlocal _id_counter
        for call in mock_session.add.call_args_list:
            obj = call[0][0]
            if getattr(obj, "id", None) is None:
                obj.id = _id_counter
                _id_counter += 1
            from backend.database.model import DomainRuleModel
            if isinstance(obj, DomainRuleModel) and obj not in added_rules:
                added_rules.append(obj)

    mock_session.flush.side_effect = _mock_flush

    # Child rule appears BEFORE parent rule in payload
    payload = {
        "workspace_id": 2,
        "expected_workspace_version": "hash_val",
        "project_id": 1,
        "target_flow_id": 10,
        "context_hash": "hash_val",
        "steps_added": [],
        "transitions_added": [],
        "transitions_updated": [],
        "rules_added": [
            {
                "temp_id": "temp_child_rule",
                "statement": "Child rule placed first",
                "name": "Child Rule",
                "parent_rule_ref": "temp_parent_rule",
            },
            {
                "temp_id": "temp_parent_rule",
                "statement": "Parent rule placed second",
                "name": "Parent Rule",
                "source_links": [{"target_kind": "feature", "target_ref": "feat-1"}],
            },
        ],
        "rule_links_added": [],
        "business_objects_added": [],
    }

    with patch(
        "backend.api.modules.requirements_core.flow_refinement.application.flow_refinement_service.load_flow_refinement_context"
    ) as mock_load_ctx:
        mock_ctx = _make_sample_context()
        mock_ctx.context_hash = "hash_val"
        mock_ctx.existing_steps = []
        mock_ctx.business_objects = []
        mock_load_ctx.return_value = mock_ctx

        result = await service.apply_refinement(
            payload=payload,
            session=mock_session,
                           workspace_id=2,
        )

        assert result["rules_added_count"] == 2
        child_rule = next(r for r in added_rules if r.statement == "Child rule placed first")
        parent_rule = next(r for r in added_rules if r.statement == "Parent rule placed second")
        assert child_rule.parent_rule_id == parent_rule.id


@pytest.mark.asyncio
async def test_apply_refinement_unresolved_parent_rule_fails():
    mock_policy = MagicMock()
    mock_policy.get_findings = AsyncMock(return_value=[])
    service = FlowRefinementService(generator=MagicMock(), finding_policy=mock_policy)
    mock_session = AsyncMock()
    mock_session.begin_nested = MagicMock(return_value=AsyncMock())

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_res
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    payload = {
        "workspace_id": 2,
        "expected_workspace_version": "hash_val",
        "project_id": 1,
        "target_flow_id": 10,
        "context_hash": "hash_val",
        "steps_added": [],
        "transitions_added": [],
        "transitions_updated": [],
        "rules_added": [
            {
                "temp_id": "temp_orphan_rule",
                "statement": "Rule with missing parent",
                "name": "Orphan Rule",
                "parent_rule_ref": "non_existent_rule_uuid",
            },
        ],
        "rule_links_added": [],
        "business_objects_added": [],
    }

    with patch(
        "backend.api.modules.requirements_core.flow_refinement.application.flow_refinement_service.load_flow_refinement_context"
    ) as mock_load_ctx:
        mock_ctx = _make_sample_context()
        mock_ctx.context_hash = "hash_val"
        mock_ctx.existing_steps = []
        mock_ctx.business_objects = []
        mock_load_ctx.return_value = mock_ctx

        with pytest.raises(ValueError) as excinfo:
            await service.apply_refinement(payload=payload, session=mock_session, workspace_id=2)
        assert "unresolved_parent_rule: non_existent_rule_uuid" in str(excinfo.value)


@pytest.mark.asyncio
async def test_apply_refinement_unresolved_bo_reference_fails():
    mock_policy = MagicMock()
    mock_policy.get_findings = AsyncMock(return_value=[])
    service = FlowRefinementService(generator=MagicMock(), finding_policy=mock_policy)
    mock_session = AsyncMock()
    mock_session.begin_nested = MagicMock(return_value=AsyncMock())

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_res
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    payload = {
        "workspace_id": 2,
        "expected_workspace_version": "hash_val",
        "project_id": 1,
        "target_flow_id": 10,
        "context_hash": "hash_val",
        "steps_added": [
            {
                "temp_id": "temp_step_1",
                "name": "Step referencing missing BO",
                "description": "Desc",
                "step_type": "systemAction",
                "input_business_object_numbers": ["NON_EXISTENT_BO_999"],
            }
        ],
        "transitions_added": [],
        "transitions_updated": [],
        "rules_added": [],
        "rule_links_added": [],
        "business_objects_added": [],
    }

    with patch(
        "backend.api.modules.requirements_core.flow_refinement.application.flow_refinement_service.load_flow_refinement_context"
    ) as mock_load_ctx:
        mock_ctx = _make_sample_context()
        mock_ctx.context_hash = "hash_val"
        mock_ctx.existing_steps = []
        mock_ctx.business_objects = []
        mock_load_ctx.return_value = mock_ctx

        with pytest.raises(ValueError) as excinfo:
            await service.apply_refinement(payload=payload, session=mock_session, workspace_id=2)
        assert "unresolved_business_object_reference: NON_EXISTENT_BO_999" in str(excinfo.value)


@pytest.mark.asyncio
async def test_apply_refinement_unresolved_actor_reference_fails():
    mock_policy = MagicMock()
    mock_policy.get_findings = AsyncMock(return_value=[])
    service = FlowRefinementService(generator=MagicMock(), finding_policy=mock_policy)
    mock_session = AsyncMock()
    mock_session.begin_nested = MagicMock(return_value=AsyncMock())

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None  # Actor not found in DB
    mock_session.execute.return_value = mock_res
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    payload = {
        "workspace_id": 2,
        "expected_workspace_version": "hash_val",
        "project_id": 1,
        "target_flow_id": 10,
        "context_hash": "hash_val",
        "steps_added": [
            {
                "temp_id": "temp_step_1",
                "name": "Step referencing missing actor",
                "description": "Desc",
                "step_type": "actorAction",
                "actor_ids": [99999],
            }
        ],
        "transitions_added": [],
        "transitions_updated": [],
        "rules_added": [],
        "rule_links_added": [],
        "business_objects_added": [],
    }

    with patch(
        "backend.api.modules.requirements_core.flow_refinement.application.flow_refinement_service.load_flow_refinement_context"
    ) as mock_load_ctx:
        mock_ctx = _make_sample_context()
        mock_ctx.context_hash = "hash_val"
        mock_ctx.existing_steps = []
        mock_ctx.business_objects = []
        mock_ctx.allowed_actor_ids = {99999}
        mock_ctx.allowed_bo_ids = {2}
        mock_load_ctx.return_value = mock_ctx

        with pytest.raises(ValueError) as excinfo:
            await service.apply_refinement(payload=payload, session=mock_session, workspace_id=2)
        assert "unresolved_actor_reference: 99999" in str(excinfo.value)


@pytest.mark.asyncio
async def test_apply_refinement_persists_bo_attributes():
    from backend.database.model import BusinessObjectAttributeModel

    mock_policy = MagicMock()
    mock_policy.get_findings = AsyncMock(return_value=[])
    service = FlowRefinementService(generator=MagicMock(), finding_policy=mock_policy)
    mock_session = AsyncMock()
    mock_session.begin_nested = MagicMock(return_value=AsyncMock())

    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    added_objects = []
    mock_session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))
    mock_session.flush = AsyncMock()

    payload = {
        "workspace_id": 2,
        "expected_workspace_version": "hash_val",
        "project_id": 1,
        "target_flow_id": 10,
        "context_hash": "hash_val",
        "steps_added": [],
        "transitions_added": [],
        "transitions_updated": [],
        "rules_added": [],
        "rule_links_added": [],
        "business_objects_added": [
            {
                "business_object_number": "BO-100",
                "business_object_name": "Invoice",
                "business_object_description": "Billing invoice",
                "business_object_attributes": [
                    {
                        "name": "amount",
                        "data_type": "decimal",
                        "description": "Total amount billed",
                        "example": "199.99",
                    }
                ],
            }
        ],
    }

    with patch(
        "backend.api.modules.requirements_core.flow_refinement.application.flow_refinement_service.load_flow_refinement_context"
    ) as mock_load_ctx:
        mock_ctx = _make_sample_context()
        mock_ctx.context_hash = "hash_val"
        mock_ctx.existing_steps = []
        mock_ctx.business_objects = []
        mock_ctx.allowed_actor_ids = {1}
        mock_ctx.allowed_bo_ids = {2}
        mock_load_ctx.return_value = mock_ctx

        await service.apply_refinement(payload=payload, session=mock_session, workspace_id=2)

        attr_models = [o for o in added_objects if isinstance(o, BusinessObjectAttributeModel)]
        assert len(attr_models) == 1
        assert attr_models[0].name == "amount"
        assert attr_models[0].data_type == "decimal"
        assert attr_models[0].confirmation_status == "ai_assumption"


@pytest.mark.asyncio
async def test_apply_refinement_persists_business_object_attributes_field():
    """Verify that when LLM generator outputs 'business_object_attributes', they are persisted."""
    from backend.database.model import BusinessObjectAttributeModel

    mock_policy = MagicMock()
    mock_policy.get_findings = AsyncMock(return_value=[])
    service = FlowRefinementService(generator=MagicMock(), finding_policy=mock_policy)
    mock_session = AsyncMock()
    mock_session.begin_nested = MagicMock(return_value=AsyncMock())

    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    added_objects = []
    mock_session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))
    mock_session.flush = AsyncMock()

    payload = {
        "workspace_id": 2,
        "expected_workspace_version": "hash_val",
        "project_id": 1,
        "target_flow_id": 10,
        "context_hash": "hash_val",
        "steps_added": [],
        "transitions_added": [],
        "transitions_updated": [],
        "rules_added": [],
        "rule_links_added": [],
        "business_objects_added": [
            {
                "business_object_number": "BO-101",
                "business_object_name": "Receipt",
                "business_object_description": "Payment receipt",
                "business_object_attributes": [
                    {
                        "name": "receipt_number",
                        "data_type": "string",
                        "description": "Unique receipt code",
                        "example": "RC-12345",
                    }
                ],
            }
        ],
    }

    with patch(
        "backend.api.modules.requirements_core.flow_refinement.application.flow_refinement_service.load_flow_refinement_context"
    ) as mock_load_ctx:
        mock_ctx = _make_sample_context()
        mock_ctx.context_hash = "hash_val"
        mock_ctx.existing_steps = []
        mock_ctx.business_objects = []
        mock_ctx.allowed_actor_ids = {1}
        mock_ctx.allowed_bo_ids = {2}
        mock_load_ctx.return_value = mock_ctx

        await service.apply_refinement(payload=payload, session=mock_session, workspace_id=2)

        attr_models = [o for o in added_objects if isinstance(o, BusinessObjectAttributeModel)]
        assert len(attr_models) == 1
        assert attr_models[0].name == "receipt_number"
        assert attr_models[0].data_type == "string"
        assert attr_models[0].confirmation_status == "ai_assumption"


@pytest.mark.asyncio
async def test_apply_refinement_out_of_radius_actor_fails():
    mock_policy = MagicMock()
    mock_policy.get_findings = AsyncMock(return_value=[])
    service = FlowRefinementService(generator=MagicMock(), finding_policy=mock_policy)
    mock_session = AsyncMock()
    mock_session.begin_nested = MagicMock(return_value=AsyncMock())
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=1))

    payload = {
        "workspace_id": 2,
        "expected_workspace_version": "hash_val",
        "project_id": 1,
        "target_flow_id": 10,
        "context_hash": "hash_val",
        "steps_added": [
            {
                "temp_id": "step-new-1",
                "name": "Step with unauthorized actor",
                "description": "",
                "step_type": "actorAction",
                "actor_ids": [99],
                "input_business_object_numbers": [],
                "output_business_object_numbers": [],
            }
        ],
        "transitions_added": [],
        "transitions_updated": [],
        "rules_added": [],
        "rule_links_added": [],
        "business_objects_added": [],
    }

    with patch(
        "backend.api.modules.requirements_core.flow_refinement.application.flow_refinement_service.load_flow_refinement_context"
    ) as mock_load_ctx:
        mock_ctx = _make_sample_context()
        mock_ctx.context_hash = "hash_val"
        mock_ctx.existing_steps = []
        mock_ctx.business_objects = []
        mock_ctx.allowed_actor_ids = {1, 2}  # 99 is outside radius
        mock_load_ctx.return_value = mock_ctx

        with pytest.raises(ValueError) as excinfo:
            await service.apply_refinement(payload=payload, session=mock_session, workspace_id=2)
        assert "step_actor_outside_local_refinement_radius: actor 99" in str(excinfo.value)


@pytest.mark.asyncio
async def test_apply_refinement_out_of_radius_bo_fails():
    mock_policy = MagicMock()
    mock_policy.get_findings = AsyncMock(return_value=[])
    service = FlowRefinementService(generator=MagicMock(), finding_policy=mock_policy)
    mock_session = AsyncMock()
    mock_session.begin_nested = MagicMock(return_value=AsyncMock())
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=1))

    payload = {
        "workspace_id": 2,
        "expected_workspace_version": "hash_val",
        "project_id": 1,
        "target_flow_id": 10,
        "context_hash": "hash_val",
        "steps_added": [
            {
                "temp_id": "step-new-1",
                "name": "Step with unauthorized BO",
                "description": "",
                "step_type": "actorAction",
                "actor_ids": [],
                "input_business_object_numbers": ["BO-99"],
                "output_business_object_numbers": [],
            }
        ],
        "transitions_added": [],
        "transitions_updated": [],
        "rules_added": [],
        "rule_links_added": [],
        "business_objects_added": [],
    }

    with patch(
        "backend.api.modules.requirements_core.flow_refinement.application.flow_refinement_service.load_flow_refinement_context"
    ) as mock_load_ctx:
        mock_ctx = _make_sample_context()
        mock_ctx.context_hash = "hash_val"
        mock_ctx.existing_steps = []
        mock_ctx.business_objects = [{"number": "BO-99", "id": 99}]
        mock_ctx.allowed_bo_ids = {1, 2}  # 99 is outside radius
        mock_load_ctx.return_value = mock_ctx

        with pytest.raises(ValueError) as excinfo:
            await service.apply_refinement(payload=payload, session=mock_session, workspace_id=2)
        assert "step_business_object_outside_local_refinement_radius: business_object BO-99" in str(excinfo.value)


def test_clean_schema_rejects_forbidden_attributes_key_and_extra_fields():
    """Verify that 'attributes' key or extra fields on business objects are strictly forbidden."""
    from pydantic import ValidationError
    from backend.api.modules.requirements_core.flow_refinement.schemas import (
        BusinessObjectAttributeItem,
        RefinedBusinessObjectItem,
        FlowRefinementCandidatePayload,
    )

    # 1. RefinedBusinessObjectItem with 'attributes' must raise ValidationError
    with pytest.raises(ValidationError) as exc1:
        RefinedBusinessObjectItem.model_validate({
            "business_object_number": "BO-1",
            "business_object_name": "Order",
            "attributes": [{"name": "price"}],
        })
    assert "extra_forbidden" in str(exc1.value)

    # 2. BusinessObjectAttributeItem with extra fields must raise ValidationError
    with pytest.raises(ValidationError) as exc2:
        BusinessObjectAttributeItem.model_validate({
            "name": "price",
            "data_type": "float",
            "unrecognized_field": "disallowed",
        })
    assert "extra_forbidden" in str(exc2.value)

    # 3. Valid clean schema passes
    valid_bo = RefinedBusinessObjectItem.model_validate({
        "business_object_number": "BO-1",
        "business_object_name": "Order",
        "business_object_attributes": [
            {"name": "price", "data_type": "float", "description": "Order price", "example": "99.9"}
        ],
    })
    assert valid_bo.business_object_name == "Order"
    assert len(valid_bo.business_object_attributes) == 1
    assert valid_bo.business_object_attributes[0].name == "price"

    # 4. FlowRefinementCandidatePayload with 'attributes' in BO raises ValidationError
    with pytest.raises(ValidationError) as exc3:
        FlowRefinementCandidatePayload.model_validate({
            "workspace_id": 2,
            "project_id": 1,
            "target_flow_id": 10,
            "business_objects_added": [
                {
                    "business_object_number": "BO-1",
                    "business_object_name": "Order",
                    "attributes": [{"name": "price"}],
                }
            ],
        })
    assert "extra_forbidden" in str(exc3.value)


@pytest.mark.asyncio
async def test_apply_refinement_flow_level_rejects_actor_or_bo_from_other_flow():
    """Verify that Flow-level refinement rejects Actors and BOs not associated with the flow's steps."""
    mock_policy = MagicMock()
    mock_policy.get_findings = AsyncMock(return_value=[])
    service = FlowRefinementService(generator=MagicMock(), finding_policy=mock_policy)
    mock_session = AsyncMock()
    mock_session.begin_nested = MagicMock(return_value=AsyncMock())
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=1))

    # Context loaded for Flow A (contains only Flow A step's actors and BOs)
    mock_ctx = _make_sample_context()
    mock_ctx.context_hash = "hash_val"
    mock_ctx.target_flow_id = 10
    mock_ctx.existing_steps = [
        {"position": 1, "step_id": 101, "logical_uuid": "s1", "actor_ids": [101], "input_business_object_ids": [201]}
    ]
    mock_ctx.business_objects = [{"id": 201, "number": "BO-FLOW-A", "name": "FlowA_Object"}]
    mock_ctx.allowed_actor_ids = {101}
    mock_ctx.allowed_bo_ids = {201}
    mock_ctx.allowed_bo_numbers = {"BO-FLOW-A"}

    # Candidate attempts to reference Actor 999 (from Flow B)
    payload_bad_actor = {
        "workspace_id": 2,
        "expected_workspace_version": "hash_val",
        "project_id": 1,
        "target_flow_id": 10,
        "target_kind": "flow",
        "context_hash": "hash_val",
        "steps_added": [
            {
                "temp_id": "step-new-1",
                "name": "Step referencing Flow B actor",
                "description": "",
                "step_type": "actorAction",
                "actor_ids": [999],  # Belongs to Flow B, not in Flow A
                "input_business_object_numbers": [],
                "output_business_object_numbers": [],
            }
        ],
    }

    with patch(
        "backend.api.modules.requirements_core.flow_refinement.application.flow_refinement_service.load_flow_refinement_context",
        return_value=mock_ctx,
    ):
        with pytest.raises(ValueError) as excinfo:
            await service.apply_refinement(payload=payload_bad_actor, session=mock_session, workspace_id=2)
        assert "step_actor_outside_local_refinement_radius: actor 999" in str(excinfo.value)

    # Candidate attempts to reference BO-FLOW-B (from Flow B)
    mock_ctx.business_objects = [
        {"id": 201, "number": "BO-FLOW-A", "name": "FlowA_Object"},
        {"id": 999, "number": "BO-FLOW-B", "name": "FlowB_Object"},  # In project DB, but not in Flow A allowed_bo_ids
    ]
    payload_bad_bo = {
        "workspace_id": 2,
        "expected_workspace_version": "hash_val",
        "project_id": 1,
        "target_flow_id": 10,
        "target_kind": "flow",
        "context_hash": "hash_val",
        "steps_added": [
            {
                "temp_id": "step-new-2",
                "name": "Step referencing Flow B BO",
                "description": "",
                "step_type": "actorAction",
                "actor_ids": [101],
                "input_business_object_numbers": ["BO-FLOW-B"],  # Belongs to Flow B, not allowed in Flow A
                "output_business_object_numbers": [],
            }
        ],
    }

    with patch(
        "backend.api.modules.requirements_core.flow_refinement.application.flow_refinement_service.load_flow_refinement_context",
        return_value=mock_ctx,
    ):
        with pytest.raises(ValueError) as excinfo:
            await service.apply_refinement(payload=payload_bad_bo, session=mock_session, workspace_id=2)
        assert "step_business_object_outside_local_refinement_radius: business_object BO-FLOW-B" in str(excinfo.value)



@pytest.mark.asyncio
async def test_apply_refinement_quality_check_detects_new_blocking_finding():
    from backend.schemas import BlockingScope, IssueSeverity

    mock_policy = MagicMock()
    # Baseline: no blocking findings
    mock_policy.get_findings = AsyncMock(side_effect=[
        [],  # baseline check
        [    # post check has a new blocking finding
            MagicMock(
                code="HOW_FLOW_DEAD_END",
                target="Step 5",
                findingId="finding-blocking-1",
                severity=IssueSeverity.BLOCKING,
                blockingScope=BlockingScope.PREVIEW,
            )
        ],
    ])

    service = FlowRefinementService(generator=MagicMock(), finding_policy=mock_policy)
    mock_session = AsyncMock()
    mock_session.begin_nested = MagicMock(return_value=AsyncMock())
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None), scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    payload = {
        "workspace_id": 2,
        "expected_workspace_version": "hash_val",
        "project_id": 1,
        "target_flow_id": 10,
        "context_hash": "hash_val",
        "steps_added": [],
        "transitions_added": [],
        "transitions_updated": [],
        "rules_added": [],
        "rule_links_added": [],
        "business_objects_added": [],
    }

    with patch(
        "backend.api.modules.requirements_core.flow_refinement.application.flow_refinement_service.load_flow_refinement_context"
    ) as mock_load_ctx:
        mock_ctx = _make_sample_context()
        mock_ctx.context_hash = "hash_val"
        mock_ctx.existing_steps = []
        mock_ctx.business_objects = []
        mock_load_ctx.return_value = mock_ctx

        with pytest.raises(ValueError) as excinfo:
            await service.apply_refinement(payload=payload, session=mock_session, workspace_id=2)
        assert "refinement_introduced_blocking_finding: HOW_FLOW_DEAD_END on Step 5" in str(excinfo.value)


@pytest.mark.asyncio
async def test_apply_refinement_quality_check_tolerates_preexisting_blocking_finding():
    from backend.schemas import BlockingScope, IssueSeverity

    preexisting_finding = MagicMock(
        code="HOW_UNCONNECTED_PREEXISTING",
        target="Step 1",
        findingId="finding-blocking-1",
        severity=IssueSeverity.BLOCKING,
        blockingScope=BlockingScope.PREVIEW,
    )

    mock_policy = MagicMock()
    # Both baseline and post have the same preexisting finding
    mock_policy.get_findings = AsyncMock(side_effect=[
        [preexisting_finding],
        [preexisting_finding],
    ])

    service = FlowRefinementService(generator=MagicMock(), finding_policy=mock_policy)
    mock_session = AsyncMock()
    mock_session.begin_nested = MagicMock(return_value=AsyncMock())
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None), scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    payload = {
        "workspace_id": 2,
        "expected_workspace_version": "hash_val",
        "project_id": 1,
        "target_flow_id": 10,
        "context_hash": "hash_val",
        "steps_added": [],
        "transitions_added": [],
        "transitions_updated": [],
        "rules_added": [],
        "rule_links_added": [],
        "business_objects_added": [],
    }

    with patch(
        "backend.api.modules.requirements_core.flow_refinement.application.flow_refinement_service.load_flow_refinement_context"
    ) as mock_load_ctx:
        mock_ctx = _make_sample_context()
        mock_ctx.context_hash = "hash_val"
        mock_ctx.existing_steps = []
        mock_ctx.business_objects = []
        mock_load_ctx.return_value = mock_ctx

        result = await service.apply_refinement(payload=payload, session=mock_session, workspace_id=2)
        assert result["flow_id"] == 10


@pytest.mark.asyncio
async def test_apply_refinement_quality_check_zero_fail_open():
    mock_policy = MagicMock()
    mock_policy.get_findings.side_effect = RuntimeError("finding detector crashed unexpectedly")

    service = FlowRefinementService(generator=MagicMock(), finding_policy=mock_policy)
    mock_session = AsyncMock()
    mock_session.begin_nested = MagicMock(return_value=AsyncMock())

    payload = {
        "workspace_id": 2,
        "expected_workspace_version": "hash_val",
        "project_id": 1,
        "target_flow_id": 10,
        "context_hash": "hash_val",
        "steps_added": [],
        "transitions_added": [],
        "transitions_updated": [],
        "rules_added": [],
        "rule_links_added": [],
        "business_objects_added": [],
    }

    with patch(
        "backend.api.modules.requirements_core.flow_refinement.application.flow_refinement_service.load_flow_refinement_context"
    ) as mock_load_ctx:
        mock_ctx = _make_sample_context()
        mock_ctx.context_hash = "hash_val"
        mock_ctx.existing_steps = []
        mock_ctx.business_objects = []
        mock_load_ctx.return_value = mock_ctx

        with pytest.raises(ValueError) as excinfo:
            await service.apply_refinement(payload=payload, session=mock_session, workspace_id=2)
        assert "refinement_quality_check_failed: finding detector crashed unexpectedly" in str(excinfo.value)


@pytest.mark.asyncio
async def test_generate_raw_done_empty_checks_all_categories():
    mock_generator = AsyncMock()
    # Output only contains transitions_updated, but no steps_added or transitions_added or rules_added
    mock_generator.generate.return_value = {
        "summary": "Updated transition label",
        "rationale": "Clarified condition",
        "steps_added": [],
        "transitions_added": [],
        "transitions_updated": [
            {
                "logical_uuid": "trans-uuid-1",
                "label": "updated label",
                "condition_text": "updated condition",
            }
        ],
        "rules_added": [],
        "rule_links_added": [],
        "business_objects_added": [],
    }

    service = FlowRefinementService(generator=mock_generator)
    mock_session = AsyncMock()
    mock_session.begin_nested = MagicMock(return_value=AsyncMock())

    with patch(
        "backend.api.modules.requirements_core.flow_refinement.application.flow_refinement_service.load_flow_refinement_context"
    ) as mock_load:
        mock_load.return_value = _make_sample_context()

        payload, ctx = await service.generate_raw(
            session=mock_session,
            project_id=1,
            target_kind="flow",
            target_id=10,
                                 workspace_id=2,
        )

        # done_empty must be False because transitions_updated is present
        assert payload["done_empty"] is False
        assert len(payload["transitions_updated"]) == 1


@pytest.mark.asyncio
async def test_apply_refinement_savepoint_atomic_rollback_real_sqlite_session():
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from backend.database.model import (
        Base,
        BranchWorkspaceModel,
        RequirementBranchModel,
        ProjectModel,
        FlowModel,
        FlowStepModel,
        FlowTransitionModel,
        DomainRuleModel,
        BusinessObjectModel,
        BusinessObjectAttributeModel,
        ActorModel,
    )
    from backend.schemas import Finding, FindingType, IssueSeverity, IssueStage

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        # Seed initial data
        proj = ProjectModel(owner_user_id=1, id=1, name="Test Proj")
        session.add(proj)
        await session.flush()
        branch = RequirementBranchModel(project_id=1, name="feature/refine", created_by_user_id=1)
        session.add(branch)
        await session.flush()
        session.add(BranchWorkspaceModel(id=2, project_id=1, branch_id=branch.id))
        await session.flush()
        actor = ActorModel(id=1, project_id=1, workspace_id=2, name="Admin")
        flow = FlowModel(id=10, project_id=1, workspace_id=2, name="Order Flow", logical_uuid="flow-uuid-10")
        step1 = FlowStepModel(id=101, flow_id=10, workspace_id=2, position=1, name="Step 1", logical_uuid="s1", step_type="actorAction")
        step2 = FlowStepModel(id=102, flow_id=10, workspace_id=2, position=2, name="Step 2", logical_uuid="s2", step_type="actorAction")
        trans1 = FlowTransitionModel(
            id=201,
            workspace_id=2,
            flow_id=10,
            project_id=1,
            source_step_id=101,
            target_step_id=102,
            logical_uuid="t1",
            condition_text="ok",
        )
        session.add_all([proj, actor, flow, step1, step2, trans1])
        await session.commit()

        # Mock finding policy that fails on post-mutation check
        mock_policy = MagicMock()
        mock_policy.get_findings = AsyncMock()
        mock_policy.get_findings.side_effect = [
            [],  # Baseline check: 0 findings
            [    # Post-mutation check: returns newly introduced blocking finding
                Finding(
                    findingId="issue-blocking-1",
                    type=FindingType.ISSUE,
                    stage=IssueStage.HOW,
                    code="HOW_UNREACHABLE_STEP",
                    title="Unreachable step",
                    description="Step cannot be reached",
                    target="flow_step:step-new-1",
                    severity=IssueSeverity.BLOCKING,
                )
            ],
        ]

        service = FlowRefinementService(finding_policy=mock_policy)

        # Context mock to match hash and whitelists
        mock_ctx = _make_sample_context()
        mock_ctx.context_hash = "server_hash_1"
        mock_ctx.existing_steps = [
            {"position": 1, "step_id": 101, "logical_uuid": "s1"},
            {"position": 2, "step_id": 102, "logical_uuid": "s2"},
        ]
        mock_ctx.business_objects = []
        mock_ctx.applicable_rules = []
        mock_ctx.allowed_actor_ids = {1}
        mock_ctx.allowed_bo_ids = set()

        payload = {
            "workspace_id": 2,
            "expected_workspace_version": "server_hash_1",
            "project_id": 1,
            "target_flow_id": 10,
            "context_hash": "server_hash_1",
            "business_objects_added": [
                {
                    "business_object_number": "BO-NEW-1",
                    "business_object_name": "Invoice",
                    "business_object_description": "Invoice object",
                    "business_object_attributes": [
                        {"name": "amount", "data_type": "float"}
                    ],
                }
            ],
            "steps_added": [
                {
                    "temp_id": "step-new-1",
                    "name": "Process Invoice",
                    "description": "Invoice processing",
                    "step_type": "actorAction",
                    "actor_ids": [1],
                    "input_business_object_numbers": ["BO-NEW-1"],
                    "output_business_object_numbers": [],
                }
            ],
            "transitions_added": [
                {
                    "temp_id": "trans-new-1",
                    "source_step_ref": 1,
                    "target_step_ref": "step-new-1",
                    "label": "Process",
                    "condition_text": "",
                }
            ],
            "transitions_updated": [],
            "rules_added": [
                {
                    "temp_id": "rule-new-1",
                    "title": "Invoice Rule",
                    "statement": "Invoice must be signed",
                    "source_links": [{"target_kind": "feature", "target_ref": "f1"}],
                }
            ],
            "rule_links_added": [],
        }

        with patch(
            "backend.api.modules.requirements_core.flow_refinement.application.flow_refinement_service.load_flow_refinement_context",
            return_value=mock_ctx,
        ):
            with pytest.raises(ValueError) as excinfo:
                await service.apply_refinement(payload=payload, session=session, workspace_id=2)
            assert "refinement_introduced_blocking_finding" in str(excinfo.value)

        # Verify 100% database rollback in real SQLite
        from sqlalchemy import select, func
        steps_count = (await session.execute(select(func.count()).select_from(FlowStepModel))).scalar()
        trans_count = (await session.execute(select(func.count()).select_from(FlowTransitionModel))).scalar()
        rules_count = (await session.execute(select(func.count()).select_from(DomainRuleModel))).scalar()
        bos_count = (await session.execute(select(func.count()).select_from(BusinessObjectModel))).scalar()
        attrs_count = (await session.execute(select(func.count()).select_from(BusinessObjectAttributeModel))).scalar()

        # Database must have rolled back to baseline perfectly
        assert steps_count == 2
        assert trans_count == 1
        assert rules_count == 0
        assert bos_count == 0
        assert attrs_count == 0

    await engine.dispose()


@pytest.mark.asyncio
async def test_apply_refinement_done_empty_acknowledged():
    mock_policy = MagicMock()
    mock_policy.get_findings = AsyncMock(return_value=[])
    service = FlowRefinementService(finding_policy=mock_policy)
    mock_session = AsyncMock()
    mock_session.begin_nested = MagicMock(return_value=AsyncMock())

    payload = {
        "workspace_id": 2,
        "expected_workspace_version": "hash_val",
        "project_id": 1,
        "target_flow_id": 10,
        "context_hash": "hash_val",
        "done_empty": True,
        "steps_added": [],
        "transitions_added": [],
        "transitions_updated": [],
        "rules_added": [],
        "rule_links_added": [],
        "business_objects_added": [],
    }

    with patch(
        "backend.api.modules.requirements_core.flow_refinement.application.flow_refinement_service.load_flow_refinement_context"
    ) as mock_load:
        mock_ctx = _make_sample_context()
        mock_ctx.context_hash = "hash_val"
        mock_load.return_value = mock_ctx

        res = await service.apply_refinement(payload=payload, session=mock_session, workspace_id=2)
        assert res["status"] == "applied"
        assert res["message"] == "done_empty_acknowledged"
        assert res["steps_added"] == 0


@pytest.mark.asyncio
async def test_apply_refinement_demotes_conflicting_default_transition():
    from backend.database.model import FlowTransitionModel
    mock_policy = MagicMock()
    mock_policy.get_findings = AsyncMock(return_value=[])
    service = FlowRefinementService(finding_policy=mock_policy)
    mock_session = AsyncMock()
    mock_session.begin_nested = MagicMock(return_value=AsyncMock())

    # Mock execute results:
    # 1. Existing default transitions: returns source_step_id 1
    # 2. Max position for step 1: returns 0
    # 3. Max position for step-new-1: returns None
    added_transitions = []
    def mock_add(entity):
        if isinstance(entity, FlowTransitionModel):
            added_transitions.append(entity)
    mock_session.add = MagicMock(side_effect=mock_add)
    mock_session.flush = AsyncMock()

    # Return source_step_id=1 as having an existing default transition
    exec_count = 0
    async def mock_execute(stmt):
        nonlocal exec_count
        exec_count += 1
        res = MagicMock()
        # default_trans_stmt: returns [1]
        res.scalars.return_value.all.return_value = [1]
        res.scalar_one_or_none.return_value = 0
        return res
    mock_session.execute = AsyncMock(side_effect=mock_execute)

    payload = {
        "workspace_id": 2,
        "expected_workspace_version": "hash_val",
        "project_id": 1,
        "target_flow_id": 10,
        "context_hash": "hash_val",
        "steps_added": [
            {
                "temp_id": "step-new-1",
                "name": "New Step",
                "description": "",
                "step_type": "actorAction",
                "actor_ids": [],
            }
        ],
        "transitions_added": [
            {
                "temp_id": "trans-new-1",
                "source_step_ref": 1,
                "target_step_ref": "step-new-1",
                "label": "Branch 1",
                "is_default": True,  # requested True, but step 1 already has default!
            }
        ],
        "transitions_updated": [],
        "rules_added": [],
        "rule_links_added": [],
        "business_objects_added": [],
    }

    with patch(
        "backend.api.modules.requirements_core.flow_refinement.application.flow_refinement_service.load_flow_refinement_context"
    ) as mock_load:
        mock_ctx = _make_sample_context()
        mock_ctx.context_hash = "hash_val"
        mock_ctx.existing_steps = [{"step_id": 1, "position": 1, "logical_uuid": "uuid-step-1"}]
        mock_load.return_value = mock_ctx

        res = await service.apply_refinement(payload=payload, session=mock_session, workspace_id=2)
        assert res["transitions_added_count"] == 1
        assert len(added_transitions) == 1
        # Crucial check: is_default was safely demoted to False to avoid constraint violation!
        assert added_transitions[0].is_default is False
