from __future__ import annotations

import os
import logging
import asyncio
import time
import hashlib
from typing import Any, Optional

from backend.api.modules.project_lifecycle.schemas.project import ProjectDetailResponse
from backend.integration.skill_backed_services.skill_imports import import_skill_module
from backend.integration.skill_backed_services.spl_export_models import SplExportOutput
from backend.integration.skill_backed_services.llm_json_client import SyncSkillBackedLLMJsonClient

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

    async def export(self, detail: ProjectDetailResponse, llm_ctx: Optional[Any] = None) -> str:
        """
        Exports project details to semantic SPL.
        Integrates LLM credentials from llm_ctx and implements caching.
        """
        if os.getenv("SPL_SEMANTIC_EXPORT_ENABLED", "true").lower() == "false":
            raise ValueError("spl_export_semantic_disabled")

        if not self._available:
            raise ValueError("spl_export_skill_unavailable")

        # Convert Pydantic ProjectDetailResponse to raw dictionaries
        detail_dict = detail.model_dump()
        payload = {
            "project": {
                "project_id": detail_dict.get("project_id", ""),
                "project_name": detail_dict.get("project_name", ""),
                "project_description": detail_dict.get("project_description", ""),
                "user_requirements": detail_dict.get("user_requirements", ""),
            },
            "actors": detail_dict.get("actors", []),
            "features": detail_dict.get("features", []),
            "business_objects": detail_dict.get("business_objects", []),
            "flows": detail_dict.get("flows", []),
            "unresolved_gates": detail_dict.get("unresolved_gates", []),
            "export_options": {
                "mode": "semantic",
                "language": "zh-CN",
                "include_trace_links": True,
                "include_warnings": True,
            }
        }

        # Dynamically extract LLM configuration credentials from llm_ctx
        api_url = getattr(llm_ctx, "api_url", None)
        api_key = getattr(llm_ctx, "api_key", None)
        model_name = getattr(llm_ctx, "model_name", None)

        llm_fingerprint_source = f"{api_url or ''}|{model_name or ''}"
        llm_fingerprint = hashlib.sha256(llm_fingerprint_source.encode("utf-8")).hexdigest()[:12]

        # Calculate snapshot hash for cache lookup
        project_json = detail.model_dump_json()
        snapshot_hash = hashlib.sha256(project_json.encode("utf-8")).hexdigest()
        cache_key = f"{detail.project_id}:semantic:{snapshot_hash}:{llm_fingerprint}"

        now = time.time()
        if cache_key in _SEMANTIC_EXPORT_CACHE:
            cached_val = _SEMANTIC_EXPORT_CACHE[cache_key]
            if now - cached_val["created_at"] < _CACHE_TTL_SECONDS:
                logger.info(f"Semantic export cache hit for project {detail.project_id}")
                return cached_val["spl_text"]

        if api_url or api_key or model_name:
            client = SyncSkillBackedLLMJsonClient(
                api_url=api_url,
                api_key=api_key,
                model_name=model_name
            )
            # Instantiate skill core dynamically using LLM context
            skill = self._core.SplSemanticExportSkill(ask_json=client.ask_json)
        else:
            # Fallback to the default pre-instantiated skill for conftest / unit tests
            skill = self._skill

        try:
            # Read overall export timeout from environment variables (default 120 seconds)
            try:
                export_timeout = float(os.getenv("SPL_SEMANTIC_EXPORT_TIMEOUT_SECONDS", "120"))
            except (ValueError, TypeError):
                export_timeout = 120.0

            # Run the synchronous skill.export inside an executor thread with wait_for timeout
            loop = asyncio.get_running_loop()
            result_dict = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    skill.export,
                    payload,
                ),
                timeout=export_timeout
            )
            
            # Validate output using SplExportOutput schema
            output = SplExportOutput.model_validate(result_dict)
            if not output.spl_text:
                raise ValueError("spl_export_invalid_skill_output")

            # Save result in cache
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
