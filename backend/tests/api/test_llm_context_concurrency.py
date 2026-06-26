"""
P4 Concurrency & Isolation Tests for Request-Scoped LLM Configuration.

Covers:
  - Two regular users concurrent isolation (URL / Authorization / Model intercepted)
  - Admin + regular user concurrent isolation
  - Exception-path ContextVar reset
  - Legacy generation endpoint (actor_generation_drafts)
  - Skill-backed generation endpoint (generation_choice_groups)
  - No-config user: AI returns 409, non-AI CRUD returns 200
  - gather-based task inheritance
  - CLI compatibility
  - Web-mode missing context error
"""
import os
import asyncio
import json
import re
import pytest
import httpx
from unittest.mock import AsyncMock, patch
from fastapi import APIRouter, Depends, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from backend.main import app
from backend.database.database import get_session, Base
from backend.database.model import (
    UserRole,
    UserLLMConfigModel,
    UserModel,
    ProjectModel,
    ChoiceGroupModel,
    ChoiceModel,
    GenerativeDraftModel,
)
from backend.api.modules.decision_workflow.public import ChoiceActionResponse
from backend.api.dependencies.llm import get_llm_context
from backend.core.llm_context import (
    current_llm_context, is_web_request_ctx,
    LLMRequestContext, LLMContextMissingError, LLMConfigError,
)
from backend.services.LLM_service import LLMHandler

DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# ---------------------------------------------------------------------------
# Test-only router that inspects context + delays to force overlap
# ---------------------------------------------------------------------------
test_router = APIRouter()


@test_router.get("/api/test-context-inspect")
async def inspect_context(llm_ctx: LLMRequestContext = Depends(get_llm_context)):
    await asyncio.sleep(0.3)
    ctx_val = current_llm_context.get()
    return {
        "api_url": llm_ctx.api_url,
        "api_key": llm_ctx.api_key,
        "model_name": llm_ctx.model_name,
        "current_var": {
            "api_url": ctx_val.api_url,
            "api_key": ctx_val.api_key,
            "model_name": ctx_val.model_name,
        } if ctx_val else None,
    }


@test_router.get("/api/test-context-gather")
async def inspect_context_gather(llm_ctx: LLMRequestContext = Depends(get_llm_context)):
    async def worker():
        await asyncio.sleep(0.1)
        ctx = current_llm_context.get()
        return ctx.api_key if ctx else None
    results = await asyncio.gather(worker(), worker())
    return {"results": results}


@test_router.get("/api/test-context-error")
async def inspect_context_error(llm_ctx: LLMRequestContext = Depends(get_llm_context)):
    """Endpoint that always raises to verify ContextVar reset on exception path."""
    raise HTTPException(status_code=500, detail="deliberate_error")


@test_router.get("/api/test-context-llm-call")
async def inspect_context_llm_call(llm_ctx: LLMRequestContext = Depends(get_llm_context)):
    import httpx
    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"{llm_ctx.api_url}/v1/chat/completions",
            json={"model": llm_ctx.model_name, "messages": []},
            headers={"Authorization": f"Bearer {llm_ctx.api_key}"}
        )
    return {"status": res.status_code}


app.include_router(test_router)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
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


def _configure_llm(client, cookie, api_url, api_key, model_name):
    client.cookies.clear()
    client.cookies.set("auth_session", cookie)
    res = client.put(
        "/api/account/llm-config",
        json={"api_url": api_url, "api_key": api_key, "model_name": model_name},
    )
    assert res.status_code == 200
    return res


def _get_async_client():
    try:
        from httpx import ASGITransport
        return httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")
    except ImportError:
        return httpx.AsyncClient(app=app, base_url="http://testserver")


async def _create_project_db(session_factory, owner_user_id, name="TestProject"):
    """Create a project directly in the DB and return (proj.id, proj.public_id)."""
    async with session_factory() as session:
        proj = ProjectModel(
            name=name,
            description="test project",
            owner_user_id=owner_user_id,
            user_requirements="test requirements",
        )
        session.add(proj)
        await session.flush()
        pid = proj.id
        pub_id = proj.public_id
        await session.commit()
    return pid, pub_id


# ---------------------------------------------------------------------------
# 1. Two regular users concurrent isolation — intercept upstream requests
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_concurrent_isolation_intercepts_upstream(llm_test_db):
    """Two users fire concurrently; we mock httpx and verify each outgoing
    request carries the correct URL, Authorization header, and Model."""
    client = TestClient(app)
    uid_a, cookie_a = _register_user(client, "intercept_a@example.com", "pass1234")
    uid_b, cookie_b = _register_user(client, "intercept_b@example.com", "pass1234")

    _configure_llm(client, cookie_a, "https://api.user-a.com", "sk-usera-key1234567890", "gpt-user-a")
    _configure_llm(client, cookie_b, "https://api.user-b.com", "sk-userb-key0987654321", "gpt-user-b")

    captured_requests = []

    async def _fake_post(self, url, *, json=None, headers=None, **kwargs):
        captured_requests.append({
            "url": str(url),
            "auth_header": headers.get("Authorization", "") if headers else "",
            "model": json.get("model", "") if json else "",
        })
        # Return a mock 200 response with valid chat completion format
        mock_resp = httpx.Response(
            200,
            json={"choices": [{"message": {"content": "pong"}}]},
            request=httpx.Request("POST", url),
        )
        return mock_resp

    _, proj_a = await _create_project_db(llm_test_db, uid_a, "ProjectA")
    _, proj_b = await _create_project_db(llm_test_db, uid_b, "ProjectB")

    with patch.object(httpx.AsyncClient, "post", _fake_post):
        async with _get_async_client() as ac:
            # Fire /api/test-context-llm-call for both users concurrently
            resp_a, resp_b = await asyncio.gather(
                ac.get("/api/test-context-llm-call", cookies={"auth_session": cookie_a}),
                ac.get("/api/test-context-llm-call", cookies={"auth_session": cookie_b}),
            )

    assert resp_a.status_code == 200
    assert resp_b.status_code == 200

    # Verify each request was routed to the correct upstream
    urls_seen = {r["url"] for r in captured_requests}
    auths_seen = {r["auth_header"] for r in captured_requests}
    models_seen = {r["model"] for r in captured_requests}

    assert "https://api.user-a.com/v1/chat/completions" in urls_seen
    assert "https://api.user-b.com/v1/chat/completions" in urls_seen
    assert "Bearer sk-usera-key1234567890" in auths_seen
    assert "Bearer sk-userb-key0987654321" in auths_seen
    assert "gpt-user-a" in models_seen
    assert "gpt-user-b" in models_seen


# ---------------------------------------------------------------------------
# 2. Admin + regular user concurrent isolation
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_admin_user_concurrent_isolation(llm_test_db, monkeypatch):
    """Admin resolves from .env; regular user resolves from DB.
    Concurrent requests must never leak credentials."""
    import backend.api.modules.auth_account.application.auth_service as auth_service
    from backend.core.security import hash_password
    invite_code = "admin_invite_secret_42"
    hashed_code = hash_password(invite_code)
    monkeypatch.setattr(auth_service, "ADMIN_INVITE_CODE_HASH", hashed_code)

    monkeypatch.setenv("LLM_API_URL", "https://api.server-admin.com")
    monkeypatch.setenv("LLM_API_KEY", "sk-server-admin-key")
    monkeypatch.setenv("LLM_MODEL_NAME", "claude-admin-model")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.7")

    client = TestClient(app)
    uid_admin, cookie_admin = _register_user(client, "admin_concur2@example.com", "pass1234", invite_code)
    uid_user, cookie_user = _register_user(client, "user_concur2@example.com", "pass1234")
    _configure_llm(client, cookie_user, "https://api.regular-user.com", "sk-regular-user-key", "gpt-regular")

    async with _get_async_client() as ac:
        resp_admin, resp_user = await asyncio.gather(
            ac.get("/api/test-context-inspect", cookies={"auth_session": cookie_admin}),
            ac.get("/api/test-context-inspect", cookies={"auth_session": cookie_user}),
        )

    assert resp_admin.status_code == 200
    assert resp_user.status_code == 200

    data_admin = resp_admin.json()
    data_user = resp_user.json()

    # Admin sees server config
    assert data_admin["api_url"] == "https://api.server-admin.com"
    assert data_admin["api_key"] == "sk-server-admin-key"
    assert data_admin["model_name"] == "claude-admin-model"
    assert data_admin["current_var"]["api_key"] == "sk-server-admin-key"

    # Regular user sees personal config
    assert data_user["api_url"] == "https://api.regular-user.com"
    assert data_user["api_key"] == "sk-regular-user-key"
    assert data_user["model_name"] == "gpt-regular"
    assert data_user["current_var"]["api_key"] == "sk-regular-user-key"


# ---------------------------------------------------------------------------
# 3. Exception path — ContextVar is reset after error
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_exception_path_context_reset(llm_test_db):
    """After a route handler raises, the ContextVar must be reset to None."""
    client = TestClient(app)
    uid, cookie = _register_user(client, "user_exception@example.com", "pass1234")
    _configure_llm(client, cookie, "https://api.err.com", "sk-error-key-12345", "gpt-err")

    async with _get_async_client() as ac:
        resp = await ac.get(
            "/api/test-context-error",
            cookies={"auth_session": cookie},
        )
    assert resp.status_code == 500
    assert resp.json()["detail"] == "Internal Server Error"

    # ContextVar must be cleaned up
    assert current_llm_context.get() is None


# ---------------------------------------------------------------------------
# 4. Legacy backend representative generation — actor_generation_drafts
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_legacy_generation_uses_scoped_context(llm_test_db):
    """POST /api/actor_generation_drafts uses llm_context_manager.
    We mock the underlying LLM call and verify the right credentials are used."""
    client = TestClient(app)
    uid, cookie = _register_user(client, "user_legacy_gen@example.com", "pass1234")
    _configure_llm(client, cookie, "https://api.legacy-gen.com", "sk-legacy-gen-key-1234", "gpt-legacy")
    _, proj_public_id = await _create_project_db(llm_test_db, uid)

    captured = {}

    original_post = httpx.AsyncClient.post

    async def _capture_post(self, url, *, json=None, headers=None, **kwargs):
        captured["url"] = str(url)
        captured["auth"] = headers.get("Authorization", "") if headers else ""
        captured["model"] = json.get("model", "") if json else ""
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"actors": []}'}}]},
            request=httpx.Request("POST", url),
        )

    with patch.object(httpx.AsyncClient, "post", _capture_post):
        client.cookies.clear()
        client.cookies.set("auth_session", cookie)
        res = client.post(
            "/api/actor_generation_drafts",
            json={"project_id": proj_public_id},
        )

    # The endpoint may return 200 or 400 (empty_actors etc.); what matters is the LLM was called with correct creds
    assert res.status_code != 422
    assert captured
    assert "legacy-gen.com" in captured["url"]
    assert "sk-legacy-gen-key-1234" in captured["auth"]
    assert captured["model"] == "gpt-legacy"



# ---------------------------------------------------------------------------
# 5. Skill-backed generation — generation_choice_groups
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_skill_generation_uses_scoped_context(llm_test_db):
    """POST /api/generation_choice_groups uses llm_context_manager.
    We mock the LLM call and verify scoped credentials are forwarded."""
    client = TestClient(app)
    uid, cookie = _register_user(client, "user_skill_gen@example.com", "pass1234")
    _configure_llm(client, cookie, "https://api.skill-gen.com", "sk-skill-gen-key-5678", "gpt-skill")
    _, proj_public_id = await _create_project_db(llm_test_db, uid)

    captured = {}

    async def _capture_post(self, url, *, json=None, headers=None, **kwargs):
        captured["url"] = str(url)
        captured["auth"] = headers.get("Authorization", "") if headers else ""
        captured["model"] = json.get("model", "") if json else ""
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"choices": []}'}}]},
            request=httpx.Request("POST", url),
        )

    with patch.object(httpx.AsyncClient, "post", _capture_post):
        client.cookies.clear()
        client.cookies.set("auth_session", cookie)
        res = client.post(
            "/api/generation_choice_groups",
            json={"project_id": proj_public_id, "generation_type": "actor"},
        )

    # The endpoint may 200 or 400; what matters is the LLM was called with the right creds
    assert res.status_code != 422
    assert captured
    assert "skill-gen.com" in captured["url"]
    assert "sk-skill-gen-key-5678" in captured["auth"]
    assert captured["model"] == "gpt-skill"


# ---------------------------------------------------------------------------
# 6. Scenario choice acceptance uses scoped context for automatic AC generation
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_scenario_choice_accept_uses_scoped_context(llm_test_db):
    client = TestClient(app)
    uid, cookie = _register_user(client, "user_choice_accept@example.com", "pass1234")
    _configure_llm(
        client,
        cookie,
        "https://api.choice-accept.com",
        "sk-choice-accept-key",
        "gpt-choice-accept",
    )
    proj_id, proj_public_id = await _create_project_db(llm_test_db, uid)

    async with llm_test_db() as session:
        group = ChoiceGroupModel(
            project_id=proj_id,
            generation_type="scenario",
            status="open",
        )
        session.add(group)
        await session.flush()
        choice = ChoiceModel(
            choice_group_id=group.id,
            title="Scenario candidate",
            patch={},
            payload={"project_id": proj_id, "scenarios": []},
            draft_type="scenario",
            apply_mode="draft_payload",
        )
        session.add(choice)
        await session.flush()
        choice_id = choice.id
        await session.commit()

    async def _accept_with_context(**kwargs):
        ctx = current_llm_context.get()
        assert ctx is not None
        assert ctx.api_url == "https://api.choice-accept.com"
        assert ctx.api_key == "sk-choice-accept-key"
        assert ctx.model_name == "gpt-choice-accept"
        return ChoiceActionResponse(
            message="choice_accepted",
            choice_id=choice_id,
            status="accepted",
        )

    with patch(
        "backend.api.modules.decision_workflow.choice_group.routes.choice_service.accept_choice",
        side_effect=_accept_with_context,
    ):
        client.cookies.clear()
        client.cookies.set("auth_session", cookie)
        res = client.post(
            f"/api/projects/{proj_public_id}/choices/{choice_id}/accept",
            json={"force": True},
        )

    assert res.status_code == 200
    assert res.json()["status"] == "accepted"
    assert current_llm_context.get() is None


@pytest.mark.anyio
async def test_blank_project_ai_branch_uses_scoped_context(llm_test_db):
    client = TestClient(app)
    uid, cookie = _register_user(client, "user_blank_ai@example.com", "pass1234")
    _configure_llm(
        client,
        cookie,
        "https://api.blank-project.com",
        "sk-blank-project-key",
        "gpt-blank-project",
    )

    async def _create_with_context(**kwargs):
        ctx = current_llm_context.get()
        assert ctx is not None
        assert ctx.api_key == "sk-blank-project-key"
        return {
            "project_id": "123",
            "project_name": "Generated",
            "project_description": "Generated description",
            "message": "project_created",
        }

    with patch(
        "backend.api.modules.project_lifecycle.routes.blank.blank_project_service.create_project",
        side_effect=_create_with_context,
    ):
        client.cookies.clear()
        client.cookies.set("auth_session", cookie)
        res = client.post(
            "/api/blank_projects",
            json={"user_requirements": "Build a test app"},
        )

    assert res.status_code == 200
    assert current_llm_context.get() is None


@pytest.mark.anyio
async def test_blank_project_complete_payload_does_not_require_llm_config(llm_test_db):
    client = TestClient(app)
    uid, cookie = _register_user(client, "user_blank_crud@example.com", "pass1234")

    client.cookies.clear()
    client.cookies.set("auth_session", cookie)
    res = client.post(
        "/api/blank_projects",
        json={
            "user_requirements": "Build a test app",
            "project_name": "Manual project",
            "project_description": "Created without AI",
        },
    )

    assert res.status_code == 200
    assert res.json()["project_name"] == "Manual project"


@pytest.mark.anyio
async def test_blank_project_empty_strings_fails_or_uses_ai(llm_test_db):
    client = TestClient(app)
    uid, cookie = _register_user(client, "user_blank_empty@example.com", "pass1234")

    client.cookies.clear()
    client.cookies.set("auth_session", cookie)
    res = client.post(
        "/api/blank_projects",
        json={
            "user_requirements": "Build a test app",
            "project_name": "",
            "project_description": "",
        },
    )

    # Since there's no LLM config, it should raise a 409 Conflict (not a 500 Internal Server Error)
    assert res.status_code == 409
    assert res.json()["detail"] == "llm_config_required"



@pytest.mark.anyio
async def test_next_suggestion_background_task_keeps_scoped_context(llm_test_db):
    client = TestClient(app)
    uid, cookie = _register_user(client, "user_next_bg@example.com", "pass1234")
    _configure_llm(
        client,
        cookie,
        "https://api.next-bg.com",
        "sk-next-bg-key",
        "gpt-next-bg",
    )
    proj_id, proj_public_id = await _create_project_db(llm_test_db, uid)
    background_context_seen = {}

    async def _get_suggestion(**kwargs):
        captured_ctx = current_llm_context.get()
        async def _background_check():
            token = current_llm_context.set(captured_ctx)
            try:
                ctx = current_llm_context.get()
                background_context_seen["api_key"] = ctx.api_key if ctx else None
            finally:
                current_llm_context.reset(token)

        kwargs["background_tasks"].add_task(_background_check)
        return {
            "project_id": proj_public_id,
            "stage": "what",
            "suggestion": {
                "source_type": "predefined",
                "code": "TEST",
                "title": "Test",
                "description": "Test",
                "status": "ready",
                "action": {},
            },
        }

    with patch(
        "backend.api.modules.diagnosis_quality.next_suggestion.routes.next_suggestion_service.get_next_suggestion",
        side_effect=_get_suggestion,
    ):
        client.cookies.clear()
        client.cookies.set("auth_session", cookie)
        res = client.get(
            f"/api/projects/{proj_public_id}/next-suggestion",
            params={"stage": "what"},
        )

    assert res.status_code == 200
    assert background_context_seen["api_key"] == "sk-next-bg-key"
    assert current_llm_context.get() is None


@pytest.mark.anyio
async def test_defer_project_choice_requires_llm_config(llm_test_db):
    client = TestClient(app)
    uid, cookie = _register_user(client, "user_defer_noconfig@example.com", "pass1234")
    group_id = "pcg_defer_context"

    async with llm_test_db() as session:
        session.add(
            GenerativeDraftModel(
                owner_user_id=uid,
                project_id=None,
                draft_id=group_id,
                draft_type="project_creation_choice_group",
                payload={"status": "open"},
            )
        )
        await session.commit()

    client.cookies.clear()
    client.cookies.set("auth_session", cookie)
    res = client.post(f"/api/project_creation_choice_groups/{group_id}/defer")

    assert res.status_code == 409
    assert res.json()["detail"] == "llm_config_required"



# ---------------------------------------------------------------------------
# 7. No-config user: AI returns 409, non-AI CRUD returns 200
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_noconfig_user_ai_409_crud_200(llm_test_db):
    """A user without LLM config should get 409 on AI endpoints
    but still succeed on non-AI CRUD endpoints."""
    client = TestClient(app)
    uid, cookie = _register_user(client, "user_noconfig2@example.com", "pass1234")
    _, proj_public_id = await _create_project_db(llm_test_db, uid)

    client.cookies.clear()
    client.cookies.set("auth_session", cookie)

    # AI endpoint → 409 (no LLM config)
    res_ai = client.post(
        "/api/actor_generation_drafts",
        json={"project_id": proj_public_id},
    )
    assert res_ai.status_code == 409
    assert res_ai.json()["detail"] == "llm_config_required"

    # AI test endpoint → 409
    res_test = client.get("/api/test-context-inspect")
    assert res_test.status_code == 409
    assert res_test.json()["detail"] == "llm_config_required"

    # CRUD endpoint → 200 (project list does not require LLM)
    res_projects = client.get("/api/projects")
    assert res_projects.status_code == 200

    # CRUD endpoint → 200 (project detail)
    res_detail = client.get(f"/api/projects/{proj_public_id}")
    assert res_detail.status_code == 200


# ---------------------------------------------------------------------------
# 7. No-config user: /api/test-context-inspect also returns 409
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_noconfig_user_llm_test_409(llm_test_db):
    """The test-context-inspect diagnostic endpoint must also honor request-scoped config:
    a user with no config gets 409, not server config."""
    client = TestClient(app)
    uid, cookie = _register_user(client, "user_noconfig_llmtest@example.com", "pass1234")

    client.cookies.clear()
    client.cookies.set("auth_session", cookie)
    res = client.get("/api/test-context-inspect")
    assert res.status_code == 409
    assert res.json()["detail"] == "llm_config_required"


# ---------------------------------------------------------------------------
# 8. Gather-based async task inheritance
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_llm_context_gather_inheritance(llm_test_db):
    client = TestClient(app)
    uid, cookie = _register_user(client, "user_gather2@example.com", "pass1234")
    _configure_llm(client, cookie, "https://api.gather.com", "sk-gather-key", "gpt-gather")

    async with _get_async_client() as ac:
        resp = await ac.get(
            "/api/test-context-gather",
            cookies={"auth_session": cookie},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["results"] == ["sk-gather-key", "sk-gather-key"]


# ---------------------------------------------------------------------------
# 9. Missing config 409 (Conflict)
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_llm_context_missing_config_conflict(llm_test_db):
    client = TestClient(app)
    uid, cookie = _register_user(client, "user_noconfig3@example.com", "pass1234")

    async with _get_async_client() as ac:
        resp = await ac.get(
            "/api/test-context-inspect",
            cookies={"auth_session": cookie},
        )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "llm_config_required"


# ---------------------------------------------------------------------------
# 10. CLI compatibility
# ---------------------------------------------------------------------------
def test_llm_handler_cli_compatibility(monkeypatch):
    monkeypatch.setenv("LLM_API_URL", "https://cli-env-url.com")
    monkeypatch.setenv("LLM_API_KEY", "sk-cli-env-key")
    monkeypatch.setenv("LLM_MODEL_NAME", "gpt-cli-env")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.5")

    handler = LLMHandler()
    assert handler.api_url == "https://cli-env-url.com"
    assert handler.api_key == "sk-cli-env-key"
    assert handler.model_name == "gpt-cli-env"

    handler_explicit = LLMHandler(
        api_url="https://cli-explicit-url.com",
        api_key="sk-cli-explicit-key",
        model_name="gpt-cli-explicit",
    )
    assert handler_explicit.api_url == "https://cli-explicit-url.com"
    assert handler_explicit.api_key == "sk-cli-explicit-key"
    assert handler_explicit.model_name == "gpt-cli-explicit"


# ---------------------------------------------------------------------------
# 11. Web-mode missing context error
# ---------------------------------------------------------------------------
def test_llm_handler_context_missing_error_inside_web():
    token = is_web_request_ctx.set(True)
    try:
        handler = LLMHandler()
        with pytest.raises(LLMContextMissingError):
            _ = handler.api_url
        with pytest.raises(LLMContextMissingError):
            _ = handler.api_key
        with pytest.raises(LLMContextMissingError):
            _ = handler.model_name
    finally:
        is_web_request_ctx.reset(token)


# ---------------------------------------------------------------------------
# 12. /api/llm_test does not leak server config values
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_llm_test_does_not_leak_config(llm_test_db, monkeypatch):
    """Even for a configured user, the response must NOT contain the raw
    api_url, api_key preview, model_name, or temperature values."""
    import backend.api.modules.auth_account.application.auth_service as auth_service
    from backend.core.security import hash_password
    invite_code = "admin_invite_secret_42"
    hashed_code = hash_password(invite_code)
    monkeypatch.setattr(auth_service, "ADMIN_INVITE_CODE_HASH", hashed_code)

    monkeypatch.setenv("LLM_API_URL", "https://api.secret-server.com")
    monkeypatch.setenv("LLM_API_KEY", "sk-supersecretkey1234567890")
    monkeypatch.setenv("LLM_MODEL_NAME", "gpt-4-secret")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.7")

    client = TestClient(app)
    client.cookies.clear()
    uid, cookie = _register_user(client, "admin_noleak@example.com", "pass1234", invite_code)

    async def _fake_get(self, url, **kwargs):
        return httpx.Response(200, text="ok", request=httpx.Request("GET", url))

    async def _fake_post(self, url, *, json=None, headers=None, **kwargs):
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "pong"}}]},
            request=httpx.Request("POST", url),
        )

    with patch.object(httpx.AsyncClient, "get", _fake_get), \
         patch.object(httpx.AsyncClient, "post", _fake_post):
        client.cookies.clear()
        client.cookies.set("auth_session", cookie)
        res = client.get("/api/llm_test")

    assert res.status_code == 200
    body = res.text

    # Must NOT contain raw API key or model name
    assert "sk-supersecretkey" not in body
    assert "gpt-4-secret" not in body
    # Config section should only contain boolean indicators
    config = res.json()["config"]
    assert "api_url" not in config  # no raw URL field
    assert config["api_url_configured"] is True
    assert config["api_key_configured"] is True
    assert config["model_configured"] is True
