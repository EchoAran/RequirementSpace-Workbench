import time
import httpx
import logging
from urllib.parse import urlparse
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.model import ProjectLLMConfigModel
from backend.api.modules.project_lifecycle.schemas.llm_config import (
    ProjectLLMConfigResponse,
    ProjectLLMConfigRequest,
    ProjectLLMConfigTestRequest,
    ProjectLLMConfigTestResponse,
)
from backend.core.security.encryption import encrypt_llm_api_key, decrypt_llm_api_key
from backend.core.logging import get_logger, log_event
from backend.core.logging.events import (
    LLM_CONFIG_MISSING,
    LLM_CONFIG_RESOLVED,
    LLM_CONFIG_SAVED,
)

logger = get_logger("backend.api.modules.project_lifecycle.application.llm_config_service")

class ProjectLLMConfigService:
    async def get_config(self, project_id: int, session: AsyncSession) -> ProjectLLMConfigResponse:
        stmt = select(ProjectLLMConfigModel).where(ProjectLLMConfigModel.project_id == project_id)
        res = await session.execute(stmt)
        db_config = res.scalar_one_or_none()
        if db_config:
            log_event(
                logger,
                logging.INFO,
                "auth",
                LLM_CONFIG_RESOLVED,
                "LLM config resolved",
                project_id=project_id,
                config_scope="project",
            )
            return ProjectLLMConfigResponse(
                configured=True,
                api_url=db_config.api_url,
                model_name=db_config.model_name,
                api_key_last4=db_config.api_key_last4,
            )
        log_event(
            logger,
            logging.WARNING,
            "auth",
            LLM_CONFIG_MISSING,
            "LLM config missing",
            project_id=project_id,
            config_scope="project",
        )
        return ProjectLLMConfigResponse(
            configured=False,
            api_url=None,
            model_name=None,
            api_key_last4=None,
        )

    async def update_config(
        self, project_id: int, user_id: int, req: ProjectLLMConfigRequest, session: AsyncSession
    ) -> ProjectLLMConfigResponse:
        api_url = req.api_url.strip() if req.api_url else ""
        api_key = req.api_key.strip() if req.api_key else ""
        model_name = req.model_name.strip() if req.model_name else ""

        stmt = select(ProjectLLMConfigModel).where(ProjectLLMConfigModel.project_id == project_id)
        res = await session.execute(stmt)
        db_config = res.scalar_one_or_none()

        if not api_url or not model_name or (not api_key and not db_config):
            raise ValueError("llm_config_invalid")

        if len(api_url) > 500 or len(model_name) > 255:
            raise ValueError("llm_config_invalid")

        from backend.api.modules.auth_account.public import validate_llm_url
        if not validate_llm_url(api_url):
            raise ValueError("llm_config_invalid")

        api_url = api_url.rstrip("/")
        encrypted_key = encrypt_llm_api_key(api_key) if api_key else None
        last4 = api_key[-4:] if len(api_key) >= 4 else api_key

        if db_config:
            db_config.api_url = api_url
            if encrypted_key is not None:
                db_config.encrypted_api_key = encrypted_key
                db_config.api_key_last4 = last4
            db_config.model_name = model_name
            db_config.updated_by_user_id = user_id
        else:
            db_config = ProjectLLMConfigModel(
                project_id=project_id,
                api_url=api_url,
                encrypted_api_key=encrypted_key,
                api_key_last4=last4,
                model_name=model_name,
                created_by_user_id=user_id,
                updated_by_user_id=user_id,
            )
            session.add(db_config)

        await session.flush()
        log_event(
            logger,
            logging.INFO,
            "auth",
            LLM_CONFIG_SAVED,
            "LLM config saved",
            project_id=project_id,
            user_id=user_id,
            config_scope="project",
        )
        return ProjectLLMConfigResponse(
            configured=True,
            api_url=db_config.api_url,
            model_name=db_config.model_name,
            api_key_last4=db_config.api_key_last4,
        )

    async def delete_config(self, project_id: int, session: AsyncSession) -> None:
        stmt = delete(ProjectLLMConfigModel).where(ProjectLLMConfigModel.project_id == project_id)
        await session.execute(stmt)
        await session.flush()

    async def test_config(
        self, project_id: int, req: ProjectLLMConfigTestRequest, session: AsyncSession
    ) -> ProjectLLMConfigTestResponse:
        has_any = any(p is not None for p in (req.api_url, req.api_key, req.model_name))
        stmt = select(ProjectLLMConfigModel).where(ProjectLLMConfigModel.project_id == project_id)
        res = await session.execute(stmt)
        db_config = res.scalar_one_or_none()

        if has_any:
            if req.api_url is None or req.model_name is None:
                raise ValueError("llm_config_invalid")
            api_url = req.api_url.strip()
            api_key = req.api_key.strip() if req.api_key is not None else ""
            model_name = req.model_name.strip()

            if not api_key and db_config:
                api_key = decrypt_llm_api_key(db_config.encrypted_api_key)

            if not api_url or not api_key or not model_name:
                raise ValueError("llm_config_invalid")

            if len(api_url) > 500 or len(model_name) > 255:
                raise ValueError("llm_config_invalid")

            from backend.api.modules.auth_account.public import validate_llm_url
            if not validate_llm_url(api_url):
                raise ValueError("llm_config_invalid")

            api_url = api_url.rstrip("/")
        else:
            if not db_config:
                raise ValueError("llm_config_required")
            api_url = db_config.api_url
            api_key = decrypt_llm_api_key(db_config.encrypted_api_key)
            model_name = db_config.model_name

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": "ping"}],
            "temperature": 0.0,
        }
        url = f"{api_url}/v1/chat/completions"
        host = urlparse(api_url).netloc

        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=5.0, trust_env=False) as client:
                response = await client.post(url, json=payload, headers=headers)
            status_code = response.status_code
            duration = time.time() - start_time

            if status_code != 200:
                return ProjectLLMConfigTestResponse(
                    success=False,
                    error_type="llm_config_test_failed",
                    error_detail=f"Upstream returned status {status_code}",
                )

            data = response.json()
            if "choices" in data:
                return ProjectLLMConfigTestResponse(success=True)
            else:
                return ProjectLLMConfigTestResponse(
                    success=False,
                    error_type="llm_config_test_failed",
                    error_detail="Invalid upstream response structure",
                )

        except httpx.TimeoutException:
            return ProjectLLMConfigTestResponse(
                success=False,
                error_type="llm_config_test_failed",
                error_detail="Request timed out",
            )
        except Exception as exc:
            from backend.api.modules.auth_account.public import sanitize_secrets
            err_msg = sanitize_secrets(str(exc), api_key)
            return ProjectLLMConfigTestResponse(
                success=False,
                error_type="llm_config_test_failed",
                error_detail="Connection failed or upstream error",
            )
