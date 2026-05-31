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

        # Wrap _ask_json to inject prompt constraints for all LLM calls in Kano analysis
        def custom_ask_json(prompt: str):
            chinese_instruction = (
                "\n\n[CRITICAL REQUIREMENT / 重要要求]\n"
                "1. Keep the requested JSON keys exactly as specified in the original prompt template (do not translate keys).\n"
                "2. However, all text content, descriptive values, reasons, keywords, expected features, viewpoints, and summaries inside the JSON must be written entirely in Chinese.\n"
                "1. 请保持原始 Prompt 模板中要求的 JSON Key 完全不变（切勿翻译 Key 名，例如保持 'Positive Preferences', 'Negative Preferences', 'Expected Features', 'Functional', 'Dysfunctional', 'rating', 'reason', 'Viewpoint' 等原样）。\n"
                "2. 但是，JSON 内部的所有文本描述、具体数值内容、打分理由、关键词、期望功能、总结与观点分析等 Value 必须全部且只能使用中文撰写！严禁输出任何英文叙述。"
            )
            modified_prompt = prompt + chinese_instruction
            return self._sync_llm_json_client.ask_json(modified_prompt)

        self._kano_skill._ask_json = custom_ask_json

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
