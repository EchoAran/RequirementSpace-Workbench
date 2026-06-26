import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Configure key before import
from cryptography.fernet import Fernet
if "LLM_CONFIG_ENCRYPTION_KEY" not in os.environ:
    os.environ["LLM_CONFIG_ENCRYPTION_KEY"] = "rK9PjN_wO2v5gVjHqX8zL1_pT5yW3xM8mU7bC4tN2zI="

from backend.main import app
from backend.database.database import get_session, Base
from backend.core.security import hash_password

# Set up test database for auth routes tests
DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def auth_test_db():
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


def test_user_registration_and_login_flow(auth_test_db):
    client = TestClient(app)

    # 1. Register a regular user
    reg_payload = {
        "email": "user@example.com",
        "password": "my_secure_password"
    }
    response = client.post("/api/auth/register", json=reg_payload)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["email"] == "user@example.com"
    assert res_data["role"] == "user"
    assert res_data["is_active"] is True
    assert "id" in res_data

    # Check that session cookie was set
    assert "auth_session" in client.cookies

    # 2. Get /me using active session
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"

    # 3. Log out
    response = client.post("/api/auth/logout")
    assert response.status_code == 200
    assert response.json()["message"] == "logged_out"
    assert "auth_session" not in client.cookies

    # 4. Get /me should fail with 401
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "authentication_required"


def test_duplicate_registration_fails(auth_test_db):
    client = TestClient(app)
    reg_payload = {
        "email": "dup@example.com",
        "password": "password123"
    }
    response = client.post("/api/auth/register", json=reg_payload)
    assert response.status_code == 200

    # Try again
    response = client.post("/api/auth/register", json=reg_payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "email_already_registered"


def test_admin_registration_with_invite_code(auth_test_db, monkeypatch):
    invite_code = "secret_admin_code"
    hashed_code = hash_password(invite_code)

    # Mock configuration's ADMIN_INVITE_CODE_HASH
    import backend.api.modules.auth_account.application.auth_service as auth_service
    monkeypatch.setattr(auth_service, "ADMIN_INVITE_CODE_HASH", hashed_code)

    client = TestClient(app)

    # 1. Registration fails with wrong invite code
    admin_payload_wrong = {
        "email": "admin@example.com",
        "password": "admin_password123",
        "invite_code": "wrong_code"
    }
    response = client.post("/api/auth/register", json=admin_payload_wrong)
    assert response.status_code == 400
    assert response.json()["detail"] == "invalid_invite_code"

    # 2. Registration succeeds with correct invite code
    admin_payload_correct = {
        "email": "admin@example.com",
        "password": "admin_password123",
        "invite_code": invite_code
    }
    response = client.post("/api/auth/register", json=admin_payload_correct)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["role"] == "admin"
    assert "auth_session" in client.cookies


def test_login_invalid_credentials(auth_test_db):
    client = TestClient(app)

    # Register first
    reg_payload = {
        "email": "login_test@example.com",
        "password": "password123"
    }
    client.post("/api/auth/register", json=reg_payload)
    client.post("/api/auth/logout")  # Clear cookie

    # Login with wrong password
    login_payload_wrong = {
        "email": "login_test@example.com",
        "password": "wrong_password"
    }
    response = client.post("/api/auth/login", json=login_payload_wrong)
    assert response.status_code == 400
    assert response.json()["detail"] == "invalid_credentials"

    # Login with wrong email
    login_payload_wrong_email = {
        "email": "wrong_email@example.com",
        "password": "password123"
    }
    response = client.post("/api/auth/login", json=login_payload_wrong_email)
    assert response.status_code == 400
    assert response.json()["detail"] == "invalid_credentials"


def test_login_timing_attack_protection(auth_test_db, monkeypatch):
    import backend.api.modules.auth_account.application.auth_service as auth_service

    verify_calls = []
    orig_verify = auth_service.verify_password

    def mock_verify(password, password_hash):
        verify_calls.append((password, password_hash))
        return orig_verify(password, password_hash)

    monkeypatch.setattr(auth_service, "verify_password", mock_verify)

    client = TestClient(app)

    # 1. Login with wrong email
    response = client.post("/api/auth/login", json={"email": "nonexistent@example.com", "password": "wrong_pwd"})
    assert response.status_code == 400
    assert len(verify_calls) == 1
    assert verify_calls[-1][1] == "$argon2id$v=19$m=65536,t=3,p=4$XENGAaVzTsQhMn6bjfXOGw$oax5ZVYYqD1fRVDV7+nxUvCJzoP3nADl+NO9huttT3w"

    # 2. Register a user
    client.post("/api/auth/register", json={"email": "existing@example.com", "password": "correct_password"})
    client.post("/api/auth/logout")

    verify_calls.clear()

    # 3. Login with correct email but wrong password
    response = client.post("/api/auth/login", json={"email": "existing@example.com", "password": "wrong_pwd"})
    assert response.status_code == 400
    assert len(verify_calls) == 1
    assert verify_calls[-1][1] != "$argon2id$v=19$m=65536,t=3,p=4$XENGAaVzTsQhMn6bjfXOGw$oax5ZVYYqD1fRVDV7+nxUvCJzoP3nADl+NO9huttT3w"


def test_registration_integrity_error_handling(auth_test_db, monkeypatch):
    from sqlalchemy.exc import IntegrityError

    client = TestClient(app)

    # Define a mock get_session dependency that raises IntegrityError on commit
    orig_get_session = app.dependency_overrides.get(get_session) or get_session

    async def override_get_session_integrity_err():
        async for session in orig_get_session():
            # Monkeypatch commit on this specific session instance
            async def mock_commit():
                raise IntegrityError("mock integrity error", params=None, orig=None)
            session.commit = mock_commit
            yield session

    app.dependency_overrides[get_session] = override_get_session_integrity_err

    try:
        response = client.post("/api/auth/register", json={"email": "unique@example.com", "password": "password123"})
        assert response.status_code == 400
        assert response.json()["detail"] == "email_already_registered"
    finally:
        if orig_get_session:
            app.dependency_overrides[get_session] = orig_get_session
        else:
            app.dependency_overrides.pop(get_session, None)
