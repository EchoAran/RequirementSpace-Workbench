from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
from typing import Any

from backend.api.modules.project_lifecycle.public import ProjectDetailResponse
from backend.core.llm_context import LLMRequestContext, current_llm_context
from backend.core.locale import DEFAULT_LOCALE
from backend.integration.skill_backed_services.llm_json_client import SyncSkillBackedLLMJsonClient
from backend.integration.skill_backed_services.skill_imports import import_skill_module
from backend.integration.skill_backed_services.spl_export_models import SplExportOutput
from backend.integration.skill_backed_services.spl_export_payload import build_spl_export_payload

logger = logging.getLogger(__name__)

# Light-weight in-memory cache for semantic exports (TTL: 10 minutes)
_SEMANTIC_EXPORT_CACHE: dict[str, dict[str, Any]] = {}
_CACHE_TTL_SECONDS = 600.0


class SplSemanticExportService:
    """
    Adapter service to load and execute the spl-semantic-export-skill.
    Does not fall back to local non-skill SPL generation.
    """

    def __init__(self) -> None:
        try:
            self._core = import_skill_module("spl-semantic-export-skill", "spl_semantic_export_skill.core")
            # Create default skill instance for unit testing / default runs
            client = SyncSkillBackedLLMJsonClient()
            self._skill = self._core.SplSemanticExportSkill(ask_json=client.ask_json)
            self._available = True
        except Exception as exc:
            logger.error(f"Failed to load spl-semantic-export-skill: {exc}")
            self._available = False

    async def export(self, detail: ProjectDetailResponse, llm_ctx: Any | None = None) -> str:
        """
        Exports project details to semantic SPL.
        Integrates LLM credentials from llm_ctx and implements caching.
        """
        if os.getenv("SPL_SEMANTIC_EXPORT_ENABLED", "true").lower() == "false":
            raise ValueError("spl_export_semantic_disabled")

        if not self._available:
            raise ValueError("spl_export_skill_unavailable")

        effective_context = llm_ctx or current_llm_context.get()
        context = self._resolve_llm_context(effective_context)
        payload = self._build_payload(detail, context["content_locale"])
        cache_key = self._build_cache_key(detail, context)

        now = time.time()
        cached = self._get_cached_export(cache_key, now, detail.project_id)
        if cached is not None:
            return cached
        skill = self._create_skill(context)

        try:
            result_dict = await self._execute_skill(
                skill,
                payload,
                effective_context,
                context,
            )
            output = SplExportOutput.model_validate(result_dict)
            if not output.spl_text:
                raise ValueError("spl_export_invalid_skill_output")
            _SEMANTIC_EXPORT_CACHE[cache_key] = {
                "spl_text": output.spl_text,
                "quality": output.quality,
                "warnings": output.warnings,
                "created_at": now
            }

            return output.spl_text
        except Exception as exc:
            logger.error(f"Error during spl-semantic-export-skill execution: {exc}")
            # Map compilation errors to stable string details
            if isinstance(exc, (asyncio.TimeoutError, TimeoutError)) or "timeout" in str(exc).lower():
                raise ValueError("spl_export_timeout") from exc
            if "invalid_skill_payload" in str(exc):
                raise ValueError("spl_export_invalid_skill_output") from exc
            raise ValueError("spl_export_invalid_skill_output") from exc

    @staticmethod
    def _resolve_llm_context(effective_context: LLMRequestContext | None) -> dict:
        return {
            "api_url": effective_context.api_url if effective_context else None,
            "api_key": effective_context.api_key if effective_context else None,
            "model_name": effective_context.model_name if effective_context else None,
            "content_locale": (
                (effective_context.content_locale if effective_context else None)
                or DEFAULT_LOCALE.value
            ),
            "content_locale_source": (
                (effective_context.content_locale_source if effective_context else None)
                or "default"
            ),
        }

    @staticmethod
    def _build_payload(
        detail: ProjectDetailResponse,
        content_locale: str,
    ) -> dict:
        return build_spl_export_payload(
            detail,
            mode="semantic",
            content_locale=content_locale,
        )

    @staticmethod
    def _build_cache_key(detail: ProjectDetailResponse, context: dict) -> str:
        fingerprint_source = (
            f"{context['api_url'] or ''}|{context['model_name'] or ''}"
        )
        fingerprint = hashlib.sha256(
            fingerprint_source.encode("utf-8")
        ).hexdigest()[:12]
        snapshot_hash = hashlib.sha256(
            detail.model_dump_json().encode("utf-8")
        ).hexdigest()
        return (
            f"{detail.project_id}:semantic:{context['content_locale']}:"
            f"{snapshot_hash}:{fingerprint}"
        )

    @staticmethod
    def _get_cached_export(cache_key: str, now: float, project_id) -> str | None:
        cached = _SEMANTIC_EXPORT_CACHE.get(cache_key)
        if cached and now - cached["created_at"] < _CACHE_TTL_SECONDS:
            logger.info(f"Semantic export cache hit for project {project_id}")
            return cached["spl_text"]
        return None

    def _create_skill(self, context: dict):
        if context["api_url"] or context["api_key"] or context["model_name"]:
            client = SyncSkillBackedLLMJsonClient(
                api_url=context["api_url"],
                api_key=context["api_key"],
                model_name=context["model_name"],
            )
            return self._core.SplSemanticExportSkill(ask_json=client.ask_json)
        return self._skill

    @staticmethod
    async def _execute_skill(
        skill,
        payload: dict,
        effective_context,
        context: dict,
    ) -> dict:
        try:
            export_timeout = float(
                os.getenv("SPL_SEMANTIC_EXPORT_TIMEOUT_SECONDS", "120")
            )
        except (ValueError, TypeError):
            export_timeout = 120.0

        token = None
        if effective_context is not None:
            request_context = LLMRequestContext(
                api_url=context["api_url"] or "",
                api_key=context["api_key"] or "",
                model_name=context["model_name"] or "",
                content_locale=context["content_locale"],
                content_locale_source=context["content_locale_source"],
            )
            token = current_llm_context.set(request_context)
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(skill.export, payload),
                timeout=export_timeout,
            )
        finally:
            if token is not None:
                current_llm_context.reset(token)
