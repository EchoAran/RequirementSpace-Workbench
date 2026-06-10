import os
from datetime import timedelta
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


def test_session_cookie_attributes(auth_test_db):
    client = TestClient(app)
    reg_payload = {
        "email": "cookie_test@example.com",
        "password": "password123"
    }
    response = client.post("/api/auth/register", json=reg_payload)
    assert response.status_code == 200

    # Get raw Set-Cookie header
    set_cookie = response.headers.get("set-cookie")
    assert set_cookie is not None
    assert "auth_session=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie

    from backend.core.config import AUTH_COOKIE_SECURE
    if AUTH_COOKIE_SECURE:
        assert "Secure" in set_cookie
    else:
        assert "Secure" not in set_cookie


@pytest.mark.asyncio
async def test_session_expiration(auth_test_db):
    session_factory = auth_test_db
    async with session_factory() as session:
        from backend.database.model import UserModel, AuthSessionModel, UserRole, beijing_now
        from backend.core.security import hash_session_token

        user = UserModel(
            email="expired@example.com",
            password_hash="hash",
            role=UserRole.USER.value,
            is_active=True
        )
        session.add(user)
        await session.commit()

        # Create an expired session (10 minutes ago)
        token = "expiredtoken12345678901234567890"
        token_hash = hash_session_token(token)
        expired_session = AuthSessionModel(
            user_id=user.id,
            session_token_hash=token_hash,
            expires_at=beijing_now() - timedelta(minutes=10)
        )
        session.add(expired_session)
        await session.commit()

    # Request with this expired token in cookie
    client = TestClient(app)
    client.cookies.set("auth_session", token)

    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "authentication_required"
