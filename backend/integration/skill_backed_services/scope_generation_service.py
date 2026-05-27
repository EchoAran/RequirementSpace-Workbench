from __future__ import annotations

import asyncio

from backend.api.services.scope_generation_service import ScopeGenerationService
from backend.integration.skill_backed_services.kano_scope_adapter import KanoScopeAdapter
from backend.integration.skill_backed_services.llm_json_client import SyncSkillBackedLLMJsonClient
from backend.integration.skill_backed_services.skill_imports import import_skill_module


class BackendLLMKanoSkill:
    def __init__(self, kano_skill):
        self._kano_skill = kano_skill
        self._sync_llm_json_client = SyncSkillBackedLLMJsonClient()
        self._kano_skill._ask_json = self._sync_llm_json_client.ask_json

    def analyze(self, requirement_text, feature_tree):
        return self._kano_skill.analyze(requirement_text, feature_tree)


class SkillBackedScopeGenerationService(ScopeGenerationService):
    def __init__(self):
        super().__init__()
        kano_core = import_skill_module("kano-skill", "kano_skill.core")
        self._kano_skill = BackendLLMKanoSkill(kano_core.KanoSkill())
        self._adapter = KanoScopeAdapter()

    async def _generate_preview(
        self,
        project_id: int,
        user_feedback: str | None,
        session,
    ) -> tuple[dict, dict]:
        (
            user_requirements,
            _feature_nodes,
            leaf_feature_nodes,
        ) = await self._load_project_context(
            project_id=project_id,
            session=session,
        )

        requirement_text = user_requirements
        if user_feedback:
            requirement_text = (
                f"{user_requirements}\n\nUser feedback for regeneration:\n{user_feedback}"
            )

        feature_tree = self._adapter.build_kano_feature_tree(leaf_feature_nodes)
        loop = asyncio.get_running_loop()
        raw = await loop.run_in_executor(
            None,
            self._kano_skill.analyze,
            requirement_text,
            feature_tree,
        )

        scopes = self._adapter.to_current_scopes(
            kano_result=raw,
            leaf_features=leaf_feature_nodes,
        )
        scopes = self._normalize_generated_scopes(
            raw={"scopes": scopes},
            leaf_feature_nodes=leaf_feature_nodes,
        )

        draft_payload = {
            "project_id": project_id,
            "scopes": scopes,
            "raw_kano": raw,
        }

        response_payload = self._build_response_payload(
            project_id=project_id,
            draft_payload=draft_payload,
            feature_nodes=leaf_feature_nodes,
        )

        return draft_payload, response_payload
