"""Registry for single-object and edit-mode generators, mapping target_type to generator class."""

from __future__ import annotations


class SingleObjectGeneratorRegistry:
    """Holds all registered single-object generators and dispatches by target_type.

    Each generator produces exactly one object from an interview summary.
    """

    def __init__(self):
        self._generator_map: dict[str, type] = {}

    def register(self, target_type: str, generator_cls: type) -> None:
        self._generator_map[target_type] = generator_cls

    def get(self, target_type: str):
        """Return a generator instance for the given target_type."""
        cls = self._generator_map.get(target_type)
        if cls is None:
            raise ValueError(f"unsupported_target_type: {target_type}")
        return cls()

    def has_type(self, target_type: str) -> bool:
        return target_type in self._generator_map


def create_default_generator_registry() -> SingleObjectGeneratorRegistry:
    """Create a registry pre-populated with all single-object generators."""
    from backend.core.generators.single_object.single_actor_generator import (
        SingleActorGenerator,
    )
    from backend.core.generators.single_object.single_feature_generator import (
        SingleFeatureGenerator,
    )
    from backend.core.generators.single_object.single_flow_generator import (
        SingleFlowGenerator,
    )
    from backend.core.generators.single_object.single_business_object_generator import (
        SingleBusinessObjectGenerator,
    )

    registry = SingleObjectGeneratorRegistry()
    registry.register("actor", SingleActorGenerator)
    registry.register("feature_leaf", SingleFeatureGenerator)
    registry.register("flow", SingleFlowGenerator)
    registry.register("business_object", SingleBusinessObjectGenerator)
    return registry


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
    registry.register("edit_feature_leaf", EditFeatureGenerator)
    registry.register("edit_flow", EditFlowGenerator)
    registry.register("edit_business_object", EditBusinessObjectGenerator)
    return registry
