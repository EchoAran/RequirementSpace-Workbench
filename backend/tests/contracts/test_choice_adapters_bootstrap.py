import pytest

from backend.api.bootstrap import register_choice_adapters
from backend.api.modules.decision_workflow.candidate_generation.application.generation_choice_service import (
    _adapter_registry,
    get_generation_choice_applier,
)
from backend.api.modules.decision_workflow.ports.ports import ChoiceAdapterRegistry


@pytest.fixture
def clean_adapters_registry():
    """Fixture to backup global choice adapter registries, clear them for testing, and restore them afterward."""
    # Backup
    saved_registry = dict(_adapter_registry)
    applier = get_generation_choice_applier()
    saved_applier_classes = dict(applier._adapter_classes)

    # Clear
    _adapter_registry.clear()
    applier._adapter_classes.clear()

    yield

    # Restore
    _adapter_registry.clear()
    _adapter_registry.update(saved_registry)
    applier._adapter_classes.clear()
    applier._adapter_classes.update(saved_applier_classes)


def test_choice_adapters_registration_completeness_and_idempotence(clean_adapters_registry):
    """Verify that explicit bootstrap registers all 7 choice adapters and is idempotent."""
    applier = get_generation_choice_applier()
    assert len(_adapter_registry) == 0
    assert len(applier._adapter_classes) == 0

    # 2. Call bootstrap registration
    registry = ChoiceAdapterRegistry()
    register_choice_adapters(registry)

    # 3. Verify exactly all 8 expected adapters are registered
    expected_types = {
        "actor",
        "scenario",
        "acceptance_criteria",
        "feature",
        "flow",
        "flow_refinement",
        "rule",
        "scope",
        "project_creation",
    }
    assert set(_adapter_registry.keys()) == expected_types
    assert set(applier._adapter_classes.keys()) == expected_types

    # 4. Verify idempotence
    register_choice_adapters(registry)
    assert set(_adapter_registry.keys()) == expected_types
    assert set(applier._adapter_classes.keys()) == expected_types


def test_bootstrap_preserves_local_rule_and_flow_generation():
    """Verify local rule and flow services under the unified skill bootstrap."""

    from backend.api.bootstrap import bootstrap_services
    from backend.api.modules.requirements_core.ports import (
        get_flow_generation_service,
        get_flow_refinement_service,
        get_rule_generation_service,
    )
    from backend.api.modules.requirements_core.flow.application.flow_generation_service import (
        FlowGenerationService,
    )
    from backend.api.modules.requirements_core.flow_refinement.application.flow_refinement_service import (
        FlowRefinementService,
    )
    from backend.api.modules.requirements_core.domain_rule.application.rule_generation_service import (
        RuleGenerationService,
    )

    bootstrap_services()

    flow_svc = get_flow_generation_service()
    flow_refinement_svc = get_flow_refinement_service()
    rule_svc = get_rule_generation_service()

    from backend.api.modules.requirements_core.ports import get_feature_generation_service
    from backend.integration.skill_backed_services.feature_generation_service import (
        SkillBackedFeatureGenerationService,
    )

    assert isinstance(get_feature_generation_service(), SkillBackedFeatureGenerationService)

    # Must be exact local instances, not skill-backed
    assert type(flow_svc) is FlowGenerationService
    assert type(flow_refinement_svc) is FlowRefinementService
    assert type(rule_svc) is RuleGenerationService
    assert not flow_svc.__class__.__name__.startswith("SkillBacked")
    assert not flow_refinement_svc.__class__.__name__.startswith("SkillBacked")
    assert not rule_svc.__class__.__name__.startswith("SkillBacked")
