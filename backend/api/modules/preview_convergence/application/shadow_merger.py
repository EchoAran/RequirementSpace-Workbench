from sqlalchemy.ext.asyncio import AsyncSession
from .shadow_patch_applier import PreviewShadowPatchApplier
from .shadow_scope_generator import PreviewShadowScopeGenerator
from .shadow_patch_generator import PreviewShadowPatchGenerator


class PreviewShadowMerger:
    @staticmethod
    def apply_patch_to_snapshot(base_snapshot: dict, patch: dict) -> tuple[dict, dict[str, int]]:
        return PreviewShadowPatchApplier.apply_patch_to_snapshot(base_snapshot, patch)

    @staticmethod
    async def generate_scopes_for_features(
        scope_service,
        user_requirements: str,
        feature_nodes: list,
        leaf_feature_nodes: list,
        user_feedback: str = "",
        temp_feat_to_int: dict[str, int] = None
    ) -> list[dict]:
        return await PreviewShadowScopeGenerator.generate_scopes_for_features(
            scope_service=scope_service,
            user_requirements=user_requirements,
            feature_nodes=feature_nodes,
            leaf_feature_nodes=leaf_feature_nodes,
            user_feedback=user_feedback,
            temp_feat_to_int=temp_feat_to_int,
        )

    @staticmethod
    async def generate_shadow_patch(
        service,
        project_id: int,
        base_snapshot: dict,
        session: AsyncSession = None,
        feedback: str = "",
        draft_id: str = "",
    ) -> dict:
        return await PreviewShadowPatchGenerator.generate_shadow_patch(
            service=service,
            project_id=project_id,
            base_snapshot=base_snapshot,
            session=session,
            feedback=feedback,
            draft_id=draft_id,
        )
