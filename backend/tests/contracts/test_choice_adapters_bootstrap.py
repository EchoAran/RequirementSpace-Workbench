import pytest
from backend.api.modules.decision_workflow.ports.ports import ChoiceAdapterRegistry
from backend.api.bootstrap import register_choice_adapters
from backend.api.modules.decision_workflow.candidate_generation.application.generation_choice_service import (
    _adapter_registry,
    get_generation_choice_applier,
)

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

    # 3. Verify exactly all 7 expected adapters are registered
    expected_types = {
        "actor",
        "scenario",
        "acceptance_criteria",
        "feature",
        "flow",
        "scope",
        "project_creation",
    }
    assert set(_adapter_registry.keys()) == expected_types
    assert set(applier._adapter_classes.keys()) == expected_types

    # 4. Verify idempotence
    register_choice_adapters(registry)
    assert set(_adapter_registry.keys()) == expected_types
    assert set(applier._adapter_classes.keys()) == expected_types
