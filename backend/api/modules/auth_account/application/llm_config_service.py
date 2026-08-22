import logging
import re
import time
from urllib.parse import urlparse

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.modules.auth_account.schemas.llm_config import (
    LLMConfigRequest,
    LLMConfigResponse,
    LLMConfigTestRequest,
    LLMConfigTestResponse,
)
from backend.core.logging import get_logger, log_event
from backend.core.logging.events import (
    LLM_CONFIG_MISSING,
    LLM_CONFIG_RESOLVED,
    LLM_CONFIG_SAVED,
)
from backend.core.security.encryption import decrypt_llm_api_key, encrypt_llm_api_key
from backend.database.model import UserLLMConfigModel, UserModel, UserRole
from backend.services.llm_handler_service import load_llm_config

logger = get_logger("backend.api.modules.auth_account.application.llm_config_service")


def validate_llm_url(url: str) -> bool:
    """Thoroughly validates http/https URLs."""
    if not url:
        return False
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        # Check that hostname is present and doesn't contain spaces
        if not parsed.netloc or parsed.netloc.strip() != parsed.netloc:
            return False
        if not parsed.hostname or " " in parsed.netloc:
            return False
        return True
    except Exception:
        return False


def sanitize_secrets(msg: str, key_to_remove: str | None = None) -> str:
    """Sanitize secrets like keys from message logs to prevent leakage."""
    if not msg:
        return ""
    if key_to_remove:
        msg = msg.replace(key_to_remove, "********")
    # Replace anything that looks like sk- followed by alphanumerics, underscores, and hyphens
    msg = re.sub(r"sk-[a-zA-Z0-9_\-]{8,}", "********", msg)
    # Also standard Authorization Bearer replacement
    msg = re.sub(r"Bearer\s+[a-zA-Z0-9_\-\.]+", "Bearer ********", msg, flags=re.IGNORECASE)
    return msg


class LLMConfigService:
    async def get_config(self, user: UserModel, session: AsyncSession) -> LLMConfigResponse:
        """Retrieve the current LLM configuration based on user role."""
        if user.role == UserRole.ADMIN.value:
            # Admins always read the server-level configuration from .env,
            # but we only return whether it is configured (we do not expose/copy .env details)
            server_config = load_llm_config()
            if server_config:
                log_event(
                    logger,
                    logging.INFO,
                    "auth",
                    LLM_CONFIG_RESOLVED,
                    "LLM config resolved",
                    user_id=user.id,
                    config_scope="server",
                )
                return LLMConfigResponse(
                    configured=True,
                    source="server",
                    api_url=None,
                    model_name=None,
                    api_key_last4=None,
                )
            log_event(
                logger,
                logging.WARNING,
                "auth",
                LLM_CONFIG_MISSING,
                "LLM config missing",
                user_id=user.id,
                config_scope="server",
            )
            return LLMConfigResponse(
                configured=False,
                source="server",
                api_url=None,
                model_name=None,
                api_key_last4=None,
            )

        # Regular users read from the database
        stmt = select(UserLLMConfigModel).where(UserLLMConfigModel.user_id == user.id)
        res = await session.execute(stmt)
        db_config = res.scalar_one_or_none()

        if db_config:
            log_event(
                logger,
                logging.INFO,
                "auth",
                LLM_CONFIG_RESOLVED,
                "LLM config resolved",
                user_id=user.id,
                config_scope="personal",
            )
            return LLMConfigResponse(
                configured=True,
                source="personal",
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
            user_id=user.id,
            config_scope="personal",
        )
        return LLMConfigResponse(
            configured=False,
            source=None,
            api_url=None,
            model_name=None,
            api_key_last4=None,
        )

    async def update_config(
        self, user: UserModel, req: LLMConfigRequest, session: AsyncSession
    ) -> LLMConfigResponse:
        """Update or create a regular user's personal LLM configuration."""
        if user.role == UserRole.ADMIN.value:
            raise ValueError("admin_cannot_configure_personal_llm")

        # Strip whitespace
        api_url = req.api_url.strip() if req.api_url else ""
        api_key = req.api_key.strip() if req.api_key else ""
        model_name = req.model_name.strip() if req.model_name else ""

        # Any blank value is invalid
        if not api_url or not api_key or not model_name:
            raise ValueError("llm_config_invalid")

        # Length restrictions
        if len(api_url) > 500 or len(model_name) > 255:
            raise ValueError("llm_config_invalid")

        # Must be valid http/https URL
        if not validate_llm_url(api_url):
            raise ValueError("llm_config_invalid")

        # Normalize trailing slash
        api_url = api_url.rstrip("/")

        # Encrypt the key
        encrypted_key = encrypt_llm_api_key(api_key)
        last4 = api_key[-4:] if len(api_key) >= 4 else api_key

        # Update or insert
        stmt = select(UserLLMConfigModel).where(UserLLMConfigModel.user_id == user.id)
        res = await session.execute(stmt)
        db_config = res.scalar_one_or_none()

        if db_config:
            db_config.api_url = api_url
            db_config.encrypted_api_key = encrypted_key
            db_config.api_key_last4 = last4
            db_config.model_name = model_name
        else:
            db_config = UserLLMConfigModel(
                user_id=user.id,
                api_url=api_url,
                encrypted_api_key=encrypted_key,
                api_key_last4=last4,
                model_name=model_name,
            )
            session.add(db_config)

        await session.flush()

        log_event(
            logger,
            logging.INFO,
            "auth",
            LLM_CONFIG_SAVED,
            "LLM config saved",
            user_id=user.id,
            config_scope="personal",
        )

        return LLMConfigResponse(
            configured=True,
            source="personal",
            api_url=db_config.api_url,
            model_name=db_config.model_name,
            api_key_last4=db_config.api_key_last4,
        )

    async def delete_config(self, user: UserModel, session: AsyncSession) -> None:
        """Delete personal LLM configuration for regular users."""
        if user.role == UserRole.ADMIN.value:
            raise ValueError("admin_cannot_configure_personal_llm")

        stmt = delete(UserLLMConfigModel).where(UserLLMConfigModel.user_id == user.id)
        await session.execute(stmt)
        await session.flush()

    async def test_config(
        self, user: UserModel, req: LLMConfigTestRequest, session: AsyncSession
    ) -> LLMConfigTestResponse:
        """Test LLM connectivity using either submitted or saved credentials."""
        api_url, api_key, model_name = await self._resolve_test_credentials(
            user,
            req,
            session,
        )
        return await self._execute_config_test(
            user_id=user.id,
            api_url=api_url,
            api_key=api_key,
            model_name=model_name,
        )

    async def _resolve_test_credentials(
        self,
        user: UserModel,
        req: LLMConfigTestRequest,
        session: AsyncSession,
    ) -> tuple[str, str, str]:
        if user.role == UserRole.ADMIN.value:
            server_config = load_llm_config()
            if not server_config:
                raise ValueError("server_llm_config_not_configured")
            return (
                server_config["api_url"].rstrip("/"),
                server_config["api_key"],
                server_config["model_name"],
            )

        params = [req.api_url, req.api_key, req.model_name]
        has_any = any(param is not None for param in params)
        has_all = all(param is not None for param in params)
        if has_any and not has_all:
            raise ValueError("llm_config_invalid")
        if has_all:
            return self._validate_submitted_test_credentials(req)

        stmt = select(UserLLMConfigModel).where(
            UserLLMConfigModel.user_id == user.id
        )
        res = await session.execute(stmt)
        db_config = res.scalar_one_or_none()
        if not db_config:
            raise ValueError("llm_config_required")
        return (
            db_config.api_url,
            decrypt_llm_api_key(db_config.encrypted_api_key),
            db_config.model_name,
        )

    @staticmethod
    def _validate_submitted_test_credentials(
        req: LLMConfigTestRequest,
    ) -> tuple[str, str, str]:
        api_url = req.api_url.strip()
        api_key = req.api_key.strip()
        model_name = req.model_name.strip()
        if not api_url or not api_key or not model_name:
            raise ValueError("llm_config_invalid")
        if len(api_url) > 500 or len(model_name) > 255:
            raise ValueError("llm_config_invalid")
        if not validate_llm_url(api_url):
            raise ValueError("llm_config_invalid")
        return api_url.rstrip("/"), api_key, model_name

    @staticmethod
    async def _execute_config_test(
        *,
        user_id: int,
        api_url: str,
        api_key: str,
        model_name: str,
    ) -> LLMConfigTestResponse:
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
        status_code = None
        try:
            async with httpx.AsyncClient(timeout=5.0, trust_env=False) as client:
                response = await client.post(url, json=payload, headers=headers)
            status_code = response.status_code
            duration = time.time() - start_time

            logger.info(
                f"User {user_id} LLM config test to host {host} completed in {duration:.3f}s with status {status_code}"
            )

            if status_code != 200:
                return LLMConfigTestResponse(
                    success=False,
                    error_type="llm_config_test_failed",
                    error_detail=f"Upstream returned status {status_code}",
                )

            data = response.json()
            if "choices" in data:
                return LLMConfigTestResponse(success=True)
            else:
                return LLMConfigTestResponse(
                    success=False,
                    error_type="llm_config_test_failed",
                    error_detail="Invalid upstream response structure",
                )

        except httpx.TimeoutException:
            duration = time.time() - start_time
            logger.info(
                f"User {user_id} LLM config test to host {host} timed out after {duration:.3f}s"
            )
            return LLMConfigTestResponse(
                success=False,
                error_type="llm_config_test_failed",
                error_detail="Request timed out",
            )
        except Exception as exc:
            duration = time.time() - start_time
            # Sanitize the logged exception message to prevent secret key leaks
            err_msg = sanitize_secrets(str(exc), api_key)
            logger.info(
                f"User {user_id} LLM config test to host {host} failed in {duration:.3f}s: {err_msg}"
            )
            return LLMConfigTestResponse(
                success=False,
                error_type="llm_config_test_failed",
                error_detail="Connection failed or upstream error",
            )

    async def resolve_for_user(self, user_id: int, session: AsyncSession, project_id: int | None = None) -> dict:
        """Resolve LLM credentials for internal calls (Plaintext key returned)."""
        if project_id:
            project_config = await self._resolve_project_config(
                user_id,
                project_id,
                session,
            )
            if project_config:
                return project_config

        stmt_user = select(UserModel).where(UserModel.id == user_id)
        res_user = await session.execute(stmt_user)
        user = res_user.scalar_one_or_none()
        if not user:
            raise ValueError("user_not_found")
        if user.role == UserRole.ADMIN.value:
            return self._resolve_admin_server_config(user_id, project_id)
        return await self._resolve_personal_config(
            user_id,
            project_id,
            session,
        )

    @staticmethod
    async def _resolve_project_config(
        user_id: int,
        project_id: int,
        session: AsyncSession,
    ) -> dict | None:
        from backend.database.model import ProjectLLMConfigModel

        result = await session.execute(
            select(ProjectLLMConfigModel).where(
                ProjectLLMConfigModel.project_id == project_id
            )
        )
        config = result.scalar_one_or_none()
        if not config:
            return None
        log_event(
            logger,
            logging.INFO,
            "auth",
            LLM_CONFIG_RESOLVED,
            "LLM config resolved",
            user_id=user_id,
            project_id=project_id,
            config_scope="project",
        )
        return {
            "api_url": config.api_url.rstrip("/"),
            "api_key": decrypt_llm_api_key(config.encrypted_api_key),
            "model_name": config.model_name,
        }

    @staticmethod
    def _resolve_admin_server_config(
        user_id: int,
        project_id: int | None,
    ) -> dict:
        server_config = load_llm_config()
        if not server_config:
            log_event(
                logger,
                logging.WARNING,
                "auth",
                LLM_CONFIG_MISSING,
                "LLM config missing",
                user_id=user_id,
                project_id=project_id,
                config_scope="server",
            )
            raise ValueError("server_llm_config_not_configured")
        log_event(
            logger,
            logging.INFO,
            "auth",
            LLM_CONFIG_RESOLVED,
            "LLM config resolved",
            user_id=user_id,
            project_id=project_id,
            config_scope="server",
        )
        return {
            "api_url": server_config["api_url"].rstrip("/"),
            "api_key": server_config["api_key"],
            "model_name": server_config["model_name"],
        }

    @staticmethod
    async def _resolve_personal_config(
        user_id: int,
        project_id: int | None,
        session: AsyncSession,
    ) -> dict:
        stmt_config = select(UserLLMConfigModel).where(UserLLMConfigModel.user_id == user_id)
        res_config = await session.execute(stmt_config)
        db_config = res_config.scalar_one_or_none()
        if not db_config:
            log_event(
                logger,
                logging.WARNING,
                "auth",
                LLM_CONFIG_MISSING,
                "LLM config missing",
                user_id=user_id,
                project_id=project_id,
                config_scope="personal",
            )
            raise ValueError("llm_config_required")
        log_event(
            logger,
            logging.INFO,
            "auth",
            LLM_CONFIG_RESOLVED,
            "LLM config resolved",
            user_id=user_id,
            project_id=project_id,
            config_scope="personal",
        )
        return {
            "api_url": db_config.api_url,
            "api_key": decrypt_llm_api_key(db_config.encrypted_api_key),
            "model_name": db_config.model_name,
        }
