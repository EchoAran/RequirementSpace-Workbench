from dataclasses import dataclass, field

TEMP_ID_COLLECTIONS = (
    "actors_added",
    "features_added",
    "scenarios_added",
    "business_objects_added",
    "flows_added",
    "flow_steps_added",
    "flow_transitions_added",
    "domain_rules_added",
)


@dataclass
class NegativeIdAllocator:
    temp_id_to_negative: dict[str, int] = field(default_factory=dict)
    next_negative: int = -1001

    @classmethod
    def from_patch(cls, patch: dict) -> "NegativeIdAllocator":
        allocator = cls()
        for collection_name in TEMP_ID_COLLECTIONS:
            for item in patch.get(collection_name, []):
                allocator.assign(item["temp_id"])
        return allocator

    def assign(self, temporary_id: str) -> None:
        if temporary_id in self.temp_id_to_negative:
            return
        self.temp_id_to_negative[temporary_id] = self.next_negative
        self.next_negative -= 1

    def allocate(self) -> int:
        value = self.next_negative
        self.next_negative -= 1
        return value

    def resolve(self, reference: str) -> int:
        if not reference:
            return 0
        if reference.startswith("tmp_"):
            return self.temp_id_to_negative.get(reference, 0)
        parts = reference.split(":")
        if len(parts) == 2:
            return int(parts[1])
        return 0
