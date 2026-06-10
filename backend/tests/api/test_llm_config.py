import os
import pytest
import httpx
import logging
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from backend.main import app
from backend.database.database import get_session, Base
from backend.database.model import UserRole, UserLLMConfigModel
from backend.core.security.encryption import decrypt_llm_api_key
from backend.api.services.llm_config_service import validate_llm_url, sanitize_secrets

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def llm_test_db():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_session():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = override_get_session
    yield session_factory
    app.dependency_overrides.pop(get_session, None)
    await engine.dispose()


def _register_user(client, email, password, invite_code=None):
    payload = {"email": email, "password": password}
    if invite_code:
        payload["invite_code"] = invite_code
    res = client.post("/api/auth/register", json=payload)
    assert res.status_code == 200
    cookie = client.cookies.get("auth_session")
    return res.json()["id"], cookie


def test_url_validation_logic():
    # Valid URLs
    assert validate_llm_url("http://localhost:8000") is True
    assert validate_llm_url("https://api.openai.com/v1") is True
    # Invalid URLs (malformed hosts, spaces, missing scheme etc)
    assert validate_llm_url("https:///path") is False
    assert validate_llm_url("http:// user:pass@host") is False
    assert validate_llm_url("ftp://host.com") is False
    assert validate_llm_url("not_a_url") is False
    assert validate_llm_url("") is False


def test_log_sanitization_logic():
    # Verify sk- key replacement
    leak_str = "Decryption failed with secret key: sk-log-leak-1234abc5678"
    sanitized = sanitize_secrets(leak_str)
    assert "sk-log-leak-1234abc5678" not in sanitized
    assert "********" in sanitized

    # Verify Bearer token replacement
    bearer_str = "Authorization Bearer sk-log-leak-1234abc5678"
    assert "sk-log" not in sanitize_secrets(bearer_str)


def test_regular_user_llm_config_crud(llm_test_db):
    client = TestClient(app)
    uid, cookie = _register_user(client, "user_test@example.com", "pass1234")

    client.cookies.clear()
    client.cookies.set("auth_session", cookie)

    # 1. GET initial -> configured=False
    res = client.get("/api/account/llm-config")
    assert res.status_code == 200
    data = res.json()
    assert data["configured"] is False
    assert data["source"] is None

    # 2. PUT invalid url -> 400
    res = client.put(
        "/api/account/llm-config",
        json={
            "api_url": "https:///path",
            "api_key": "mysecretkey",
            "model_name": "gpt-4",
        },
    )
    assert res.status_code == 400
    assert res.json()["detail"] == "llm_config_invalid"

    # 3. PUT valid -> success
    res = client.put(
        "/api/account/llm-config",
        json={
            "api_url": "https://my-openai-proxy.com/",
            "api_key": "sk-1234567890abcdef",
            "model_name": "gpt-4o",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["configured"] is True
    assert data["source"] == "personal"
    assert data["api_url"] == "https://my-openai-proxy.com"  # Normalization checked
    assert data["model_name"] == "gpt-4o"
    assert data["api_key_last4"] == "cdef"

    # 4. Check DB encryption
    async def verify_db_encryption():
        async with llm_test_db() as session:
            stmt = select(UserLLMConfigModel).where(UserLLMConfigModel.user_id == uid)
            db_res = await session.execute(stmt)
            cfg = db_res.scalar_one()
            assert cfg.encrypted_api_key != "sk-1234567890abcdef"
            decrypted = decrypt_llm_api_key(cfg.encrypted_api_key)
            assert decrypted == "sk-1234567890abcdef"

    import asyncio
    asyncio.get_event_loop().run_until_complete(verify_db_encryption())

    # 5. GET updated config
    res = client.get("/api/account/llm-config")
    assert res.status_code == 200
    data = res.json()
    assert data["configured"] is True
    assert data["api_url"] == "https://my-openai-proxy.com"
    assert data["model_name"] == "gpt-4o"
    assert data["api_key_last4"] == "cdef"

    # 6. DELETE config
    res = client.delete("/api/account/llm-config")
    assert res.status_code == 200
    assert res.json()["message"] == "llm_config_deleted"

    # 7. GET config again -> configured=False
    res = client.get("/api/account/llm-config")
    assert res.status_code == 200
    assert res.json()["configured"] is False


def test_admin_llm_config_crud_blocked_and_server_fallback(llm_test_db, monkeypatch):
    # Setup admin register invite code
    from backend.core.security import hash_password
    import backend.api.services.auth_service

    invite_code = "admin_invite_code_secret"
    hashed_code = hash_password(invite_code)
    monkeypatch.setattr(backend.api.services.auth_service, "ADMIN_INVITE_CODE_HASH", hashed_code)

    # Set server environment configs
    monkeypatch.setenv("LLM_API_URL", "https://env-llm-server.com/")
    monkeypatch.setenv("LLM_API_KEY", "sk-server1234567890")
    monkeypatch.setenv("LLM_MODEL_NAME", "claude-3")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.5")

    client = TestClient(app)
    uid, cookie = _register_user(client, "admin_test@example.com", "pass1234", invite_code)

    client.cookies.clear()
    client.cookies.set("auth_session", cookie)

    # 1. GET as admin -> returns configured status but hides actual .env values
    res = client.get("/api/account/llm-config")
    assert res.status_code == 200
    data = res.json()
    assert data["configured"] is True
    assert data["source"] == "server"
    assert data["api_url"] is None
    assert data["model_name"] is None
    assert data["api_key_last4"] is None

    # 2. PUT as admin -> blocked
    res = client.put(
        "/api/account/llm-config",
        json={
            "api_url": "https://my-openai-proxy.com",
            "api_key": "sk-1234567890",
            "model_name": "gpt-4",
        },
    )
    assert res.status_code == 400
    assert res.json()["detail"] == "admin_cannot_configure_personal_llm"

    # 3. DELETE as admin -> blocked
    res = client.delete("/api/account/llm-config")
    assert res.status_code == 400
    assert res.json()["detail"] == "admin_cannot_configure_personal_llm"


def test_user_ownership_isolation(llm_test_db):
    client = TestClient(app)
    uid_a, cookie_a = _register_user(client, "usera@example.com", "pass1234")
    uid_b, cookie_b = _register_user(client, "userb@example.com", "pass1234")

    # User A configure LLM
    client.cookies.clear()
    client.cookies.set("auth_session", cookie_a)
    res = client.put(
        "/api/account/llm-config",
        json={
            "api_url": "https://usera.com",
            "api_key": "usera-key",
            "model_name": "usera-model",
        },
    )
    assert res.status_code == 200

    # User B checks config -> configured=False (isolation verify)
    client.cookies.clear()
    client.cookies.set("auth_session", cookie_b)
    res = client.get("/api/account/llm-config")
    assert res.status_code == 200
    assert res.json()["configured"] is False


def test_llm_connectivity_checks(llm_test_db, monkeypatch):
    client = TestClient(app)
    uid, cookie = _register_user(client, "user_conn@example.com", "pass1234")

    client.cookies.clear()
    client.cookies.set("auth_session", cookie)

    # Mock response classes
    class MockResponse:
        def __init__(self, status_code, json_data):
            self.status_code = status_code
            self._json_data = json_data
            self.text = str(json_data)

        def json(self):
            return self._json_data

    # Mock client connection success
    async def mock_post_success(*args, **kwargs):
        url = args[1] if len(args) > 1 else kwargs.get("url", "")
        assert url.endswith("/v1/chat/completions")
        headers = kwargs.get("headers", {})
        assert headers["Authorization"] == "Bearer sk-submitted-key"
        json_body = kwargs.get("json", {})
        assert json_body["model"] == "submitted-model"
        assert json_body["messages"] == [{"role": "user", "content": "ping"}]
        return MockResponse(200, {"choices": [{"message": {"content": "pong"}}]})

    # 1. Success test
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post_success)
    res = client.post(
        "/api/account/llm-config/test",
        json={
            "api_url": "https://test-upstream.com/",
            "api_key": "sk-submitted-key",
            "model_name": "submitted-model",
        },
    )
    assert res.status_code == 200
    assert res.json()["success"] is True

    # Mock client timeout
    async def mock_post_timeout(*args, **kwargs):
        raise httpx.TimeoutException("mock timeout")

    # 2. Timeout test
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post_timeout)
    res = client.post(
        "/api/account/llm-config/test",
        json={
            "api_url": "https://test-upstream.com",
            "api_key": "sk-submitted-key",
            "model_name": "submitted-model",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert data["error_type"] == "llm_config_test_failed"
    assert "timed out" in data["error_detail"].lower()

    # Mock invalid response choices format
    async def mock_post_bad_json(*args, **kwargs):
        return MockResponse(200, {"bad_choices": []})

    # 3. Bad upstream JSON test
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post_bad_json)
    res = client.post(
        "/api/account/llm-config/test",
        json={
            "api_url": "https://test-upstream.com",
            "api_key": "sk-submitted-key",
            "model_name": "submitted-model",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert data["error_type"] == "llm_config_test_failed"
    assert "structure" in data["error_detail"].lower()


def test_admin_bypass_test_blocked(llm_test_db, monkeypatch):
    # Setup admin register invite code
    from backend.core.security import hash_password
    import backend.api.services.auth_service

    invite_code = "admin_invite_code_secret"
    hashed_code = hash_password(invite_code)
    monkeypatch.setattr(backend.api.services.auth_service, "ADMIN_INVITE_CODE_HASH", hashed_code)

    # Set server environment configs
    monkeypatch.setenv("LLM_API_URL", "https://env-llm-server.com")
    monkeypatch.setenv("LLM_API_KEY", "sk-server-key-env")
    monkeypatch.setenv("LLM_MODEL_NAME", "server-model-env")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.5")

    client = TestClient(app)
    uid, cookie = _register_user(client, "admin_conn_test@example.com", "pass1234", invite_code)

    client.cookies.clear()
    client.cookies.set("auth_session", cookie)

    # Mock response classes
    class MockResponse:
        def __init__(self, status_code, json_data):
            self.status_code = status_code
            self._json_data = json_data

        def json(self):
            return self._json_data

    # Mock client connection success
    async def mock_post_verify(*args, **kwargs):
        url = args[1] if len(args) > 1 else kwargs.get("url", "")
        # Check that it target the env configurations, NOT malicious request body values!
        assert url == "https://env-llm-server.com/v1/chat/completions"
        headers = kwargs.get("headers", {})
        assert headers["Authorization"] == "Bearer sk-server-key-env"
        json_body = kwargs.get("json", {})
        assert json_body["model"] == "server-model-env"
        return MockResponse(200, {"choices": [{"message": {"content": "pong"}}]})

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post_verify)

    # Submit test with body overrides, verifying that admin ignores it and runs against env config instead
    res = client.post(
        "/api/account/llm-config/test",
        json={
            "api_url": "https://malicious.io",
            "api_key": "sk-malicious-leak",
            "model_name": "malicious-model",
        },
    )
    assert res.status_code == 200
    assert res.json()["success"] is True


def test_exception_sanitization_leak_protection(llm_test_db, monkeypatch):
    client = TestClient(app)
    uid, cookie = _register_user(client, "leak_test@example.com", "pass1234")

    client.cookies.clear()
    client.cookies.set("auth_session", cookie)

    # Mock httpx AsyncClient post to raise an exception containing a secret key
    async def mock_post_with_key(*args, **kwargs):
        raise httpx.ConnectError("Connection failed to upstream using secret key: sk-log-leak-1234abc5678")

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post_with_key)

    # Capture logs to verify sanitization
    logger = logging.getLogger("backend.api.services.llm_config_service")
    orig_level = logger.level
    logger.setLevel(logging.INFO)
    log_messages = []

    class MockLogHandler(logging.Handler):
        def emit(self, record):
            log_messages.append(record.getMessage())

    handler = MockLogHandler()
    logger.addHandler(handler)

    try:
        res = client.post(
            "/api/account/llm-config/test",
            json={
                "api_url": "https://my-openai-proxy.com",
                "api_key": "sk-log-leak-1234abc5678",
                "model_name": "gpt-4",
            },
        )
        assert res.status_code == 200
        # Check that error_detail is sanitized and does not leak the key
        assert "sk-log-leak-1234abc5678" not in res.json()["error_detail"]

        # Check that logged messages do NOT leak the secret key
        assert len(log_messages) > 0
        for log_msg in log_messages:
            assert "sk-log-leak-1234abc5678" not in log_msg
            assert "sk-log-leak" not in log_msg
    finally:
        logger.removeHandler(handler)
        logger.setLevel(orig_level)


def test_test_config_length_validation(llm_test_db):
    client = TestClient(app)
    uid, cookie = _register_user(client, "user_len@example.com", "pass1234")

    client.cookies.clear()
    client.cookies.set("auth_session", cookie)

    # 1. 640 chars URL should be rejected (400)
    long_url = "https://example.com/" + "a" * 620
    res = client.post(
        "/api/account/llm-config/test",
        json={
            "api_url": long_url,
            "api_key": "mysecretkey",
            "model_name": "gpt-4",
        },
    )
    assert res.status_code == 400
    assert res.json()["detail"] == "llm_config_invalid"

    # 2. 300 chars model should be rejected (400)
    long_model = "m" * 300
    res = client.post(
        "/api/account/llm-config/test",
        json={
            "api_url": "https://example.com",
            "api_key": "mysecretkey",
            "model_name": long_model,
        },
    )
    assert res.status_code == 400
    assert res.json()["detail"] == "llm_config_invalid"
