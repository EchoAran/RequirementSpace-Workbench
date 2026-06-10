import time
import httpx
import logging
import re
from urllib.parse import urlparse
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.model import UserLLMConfigModel, UserModel, UserRole
from backend.api.schemas.account_schema import (
    LLMConfigResponse,
    LLMConfigRequest,
    LLMConfigTestRequest,
    LLMConfigTestResponse,
)
from backend.core.security.encryption import encrypt_llm_api_key, decrypt_llm_api_key
from backend.services.LLM_service import load_llm_config

logger = logging.getLogger(__name__)


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
                return LLMConfigResponse(
                    configured=True,
                    source="server",
                    api_url=None,
                    model_name=None,
                    api_key_last4=None,
                )
            else:
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
            return LLMConfigResponse(
                configured=True,
                source="personal",
                api_url=db_config.api_url,
                model_name=db_config.model_name,
                api_key_last4=db_config.api_key_last4,
            )
        else:
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
        # 1. Resolve credentials to test
        if user.role == UserRole.ADMIN.value:
            # Admins must ONLY test using the server configuration from .env
            server_config = load_llm_config()
            if not server_config:
                raise ValueError("server_llm_config_not_configured")
            api_url = server_config["api_url"].rstrip("/")
            api_key = server_config["api_key"]
            model_name = server_config["model_name"]
        else:
            # Regular user checks submitted parameters or saved configuration
            params = [req.api_url, req.api_key, req.model_name]
            has_any = any(p is not None for p in params)
            has_all = all(p is not None for p in params)

            if has_any and not has_all:
                raise ValueError("llm_config_invalid")

            if has_all:
                api_url = req.api_url.strip()
                api_key = req.api_key.strip()
                model_name = req.model_name.strip()

                if not api_url or not api_key or not model_name:
                    raise ValueError("llm_config_invalid")

                if len(api_url) > 500 or len(model_name) > 255:
                    raise ValueError("llm_config_invalid")

                if not validate_llm_url(api_url):
                    raise ValueError("llm_config_invalid")

                api_url = api_url.rstrip("/")
            else:
                # Use saved config
                stmt = select(UserLLMConfigModel).where(UserLLMConfigModel.user_id == user.id)
                res = await session.execute(stmt)
                db_config = res.scalar_one_or_none()
                if not db_config:
                    raise ValueError("llm_config_required")
                api_url = db_config.api_url
                api_key = decrypt_llm_api_key(db_config.encrypted_api_key)
                model_name = db_config.model_name

        # 2. Execute POST request
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
                f"User {user.id} LLM config test to host {host} completed in {duration:.3f}s with status {status_code}"
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
                f"User {user.id} LLM config test to host {host} timed out after {duration:.3f}s"
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
                f"User {user.id} LLM config test to host {host} failed in {duration:.3f}s: {err_msg}"
            )
            return LLMConfigTestResponse(
                success=False,
                error_type="llm_config_test_failed",
                error_detail="Connection failed or upstream error",
            )

    async def resolve_for_user(self, user_id: int, session: AsyncSession) -> dict:
        """Resolve LLM credentials for internal calls (Plaintext key returned)."""
        # Load user first to check role
        stmt_user = select(UserModel).where(UserModel.id == user_id)
        res_user = await session.execute(stmt_user)
        user = res_user.scalar_one_or_none()

        if not user:
            raise ValueError("user_not_found")

        if user.role == UserRole.ADMIN.value:
            server_config = load_llm_config()
            if not server_config:
                raise ValueError("server_llm_config_not_configured")
            return {
                "api_url": server_config["api_url"].rstrip("/"),
                "api_key": server_config["api_key"],
                "model_name": server_config["model_name"],
            }

        # Regular user
        stmt_config = select(UserLLMConfigModel).where(UserLLMConfigModel.user_id == user_id)
        res_config = await session.execute(stmt_config)
        db_config = res_config.scalar_one_or_none()

        if not db_config:
            raise ValueError("llm_config_required")

        return {
            "api_url": db_config.api_url,
            "api_key": decrypt_llm_api_key(db_config.encrypted_api_key),
            "model_name": db_config.model_name,
        }
