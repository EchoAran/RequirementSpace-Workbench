import asyncio


class PreviewShadowScopeGenerator:
    @staticmethod
    async def generate_scopes_for_features(
        scope_service,
        user_requirements: str,
        feature_nodes: list,
        leaf_feature_nodes: list,
        user_feedback: str = "",
        temp_feat_to_int: dict[str, int] = None
    ) -> list[dict]:
        """
        Generates scopes using the real registered scope generation service
        (either skill-backed or legacy), without querying database project context.
        """
        if hasattr(scope_service, "_kano_skill"):
            requirement_text = user_requirements
            if user_feedback:
                requirement_text = (
                    f"{user_requirements}\n\nUser feedback for regeneration:\n{user_feedback}"
                )
            
            feature_tree = scope_service._adapter.build_kano_feature_tree(leaf_feature_nodes)
            raw = await asyncio.to_thread(
                scope_service._kano_skill.analyze,
                requirement_text,
                feature_tree,
            )
            
            scopes = scope_service._adapter.to_current_scopes(
                kano_result=raw,
                leaf_features=leaf_feature_nodes,
            )
            
            if temp_feat_to_int:
                for sc in scopes:
                    fid = sc.get("feature_id")
                    if isinstance(fid, str) and fid in temp_feat_to_int:
                        sc["feature_id"] = temp_feat_to_int[fid]
                    elif isinstance(fid, str) and f"tmp_feature_{fid}" in temp_feat_to_int:
                        sc["feature_id"] = temp_feat_to_int[f"tmp_feature_{fid}"]
            
            normalized_scopes = scope_service._normalize_generated_scopes(
                raw={"scopes": scopes},
                leaf_feature_nodes=leaf_feature_nodes,
            )
            return normalized_scopes
        else:
            from backend.core.generators.scopes_generator import ScopesGeneratorInput
            raw = await scope_service._scopes_generator.generate(
                ScopesGeneratorInput(
                    user_requirements=user_requirements,
                    features=feature_nodes,
                    user_feedback=user_feedback,
                )
            )
            
            if temp_feat_to_int and "scopes" in raw:
                for sc in raw["scopes"]:
                    fid = sc.get("feature_id")
                    if isinstance(fid, str) and fid in temp_feat_to_int:
                        sc["feature_id"] = temp_feat_to_int[fid]
                    elif isinstance(fid, str) and f"tmp_feature_{fid}" in temp_feat_to_int:
                        sc["feature_id"] = temp_feat_to_int[f"tmp_feature_{fid}"]
            
            normalized_scopes = scope_service._normalize_generated_scopes(
                raw=raw,
                leaf_feature_nodes=leaf_feature_nodes,
            )
            return normalized_scopes
