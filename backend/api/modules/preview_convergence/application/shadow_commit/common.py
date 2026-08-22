from dataclasses import dataclass, field
from typing import Any


def _resolve_id(reference: Any, temporary_ids: dict[str, int]) -> int:
    if not reference:
        return 0
    reference_text = str(reference)
    if reference_text.startswith("tmp_"):
        return temporary_ids[reference_text]
    if ":" in reference_text:
        return int(reference_text.split(":")[1])
    return int(reference_text)

@dataclass
class _CommitIdMaps:
    actors: dict[str, int] = field(default_factory=dict)
    features: dict[str, int] = field(default_factory=dict)
    scenarios: dict[str, int] = field(default_factory=dict)
    business_objects: dict[str, int] = field(default_factory=dict)
    flows: dict[str, int] = field(default_factory=dict)
    steps: dict[str, int] = field(default_factory=dict)

    def resolve_actor(self, reference: Any) -> int:
        return _resolve_id(reference, self.actors)

    def resolve_feature(self, reference: Any) -> int:
        return _resolve_id(reference, self.features)

    def resolve_scenario(self, reference: Any) -> int:
        return _resolve_id(reference, self.scenarios)

    def resolve_business_object(self, reference: Any) -> int:
        return _resolve_id(reference, self.business_objects)

    def resolve_flow(self, reference: Any) -> int:
        return _resolve_id(reference, self.flows)

    def resolve_step(self, reference: Any) -> int:
        return _resolve_id(reference, self.steps)
