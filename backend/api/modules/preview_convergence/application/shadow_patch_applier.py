import copy

from .shadow_patch import (
    NegativeIdAllocator,
    apply_how_nodes,
    apply_what_nodes,
    finalize_what_nodes,
)


def _apply_project_metadata(snapshot: dict, base_snapshot: dict) -> None:
    snapshot["project_id"] = base_snapshot.get("project_id")
    snapshot["project_name"] = base_snapshot.get("name")
    snapshot["project_description"] = base_snapshot.get("description")
    snapshot["user_requirements"] = base_snapshot.get(
        "user_requirements"
    )
    snapshot["kano_status"] = "generated"


class PreviewShadowPatchApplier:
    @staticmethod
    def apply_patch_to_snapshot(
        base_snapshot: dict,
        patch: dict,
    ) -> tuple[dict, dict[str, int]]:
        """
        Merge a patch into a copied snapshot using negative transient IDs.
        """
        snapshot = copy.deepcopy(base_snapshot)
        allocator = NegativeIdAllocator.from_patch(patch)
        existing_features, added_features = apply_what_nodes(
            snapshot,
            patch,
            allocator,
        )
        apply_how_nodes(snapshot, patch, allocator)
        finalize_what_nodes(
            snapshot,
            patch,
            allocator,
            existing_features,
            added_features,
        )
        _apply_project_metadata(snapshot, base_snapshot)
        return snapshot, allocator.temp_id_to_negative
