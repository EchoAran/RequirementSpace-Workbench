"""Registry for edit-mode generators, mapping edit_* target_type to generator class."""

from __future__ import annotations


class EditGeneratorRegistry:
    """Holds all registered edit generators and dispatches by target_type."""

    def __init__(self):
        self._map: dict[str, type] = {}

    def register(self, target_type: str, generator_cls: type) -> None:
        self._map[target_type] = generator_cls

    def get(self, target_type: str):
        cls = self._map.get(target_type)
        if cls is None:
            raise ValueError(f"unsupported_target_type: {target_type}")
        return cls()

    def has_type(self, target_type: str) -> bool:
        return target_type in self._map


def create_default_edit_generator_registry() -> EditGeneratorRegistry:
    """Create a registry pre-populated with all edit-mode generators."""
    from backend.core.generators.single_object.edit_actor_generator import (
        EditActorGenerator,
    )
    from backend.core.generators.single_object.edit_feature_generator import (
        EditFeatureGenerator,
    )
    from backend.core.generators.single_object.edit_flow_generator import (
        EditFlowGenerator,
    )
    from backend.core.generators.single_object.edit_business_object_generator import (
        EditBusinessObjectGenerator,
    )

    registry = EditGeneratorRegistry()
    registry.register("edit_actor", EditActorGenerator)
    registry.register("edit_feature", EditFeatureGenerator)
    registry.register("edit_flow", EditFlowGenerator)
    registry.register("edit_business_object", EditBusinessObjectGenerator)
    return registry
