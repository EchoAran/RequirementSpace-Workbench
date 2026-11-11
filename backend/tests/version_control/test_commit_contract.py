"""
Phase 3 Contract Tests for Commit Read-Only & Expected-Head Constraints.

覆盖两项 P1 验收：
1. 创建提交必须携带预期 head（缺失时 422）。
2. 需求模型写接口携带 commit_id 时必须被显式拒绝（403），而不是被静默忽略后写入当前工作区。
"""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.dependencies.ownership import require_owned_generative_draft
from backend.database.database import Base, get_session
from backend.main import app

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_client():
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
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
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_session, None)
    await engine.dispose()


def _register_login_and_create_project(client: TestClient) -> int:
    """注册并登录用户、创建项目，返回项目的 public id。"""
    client.post("/api/auth/register", json={"email": "vc@test.example", "password": "password123"})
    client.post("/api/auth/login", json={"email": "vc@test.example", "password": "password123"})
    res = client.post(
        "/api/blank_projects",
        json={
            "user_requirements": "Version control contract test",
            "project_name": "VC Contract",
            "project_description": "Desc",
        },
    )
    project_id = res.json()["projectId"]
    client.put(
        "/api/account/llm-config",
        json={
            "api_url": "https://api.openai.com/v1",
            "api_key": "sk-dummy-test-key-string-long-enough",
            "model_name": "gpt-4-turbo",
        },
    )
    return project_id


def test_create_commit_without_expected_head_is_rejected(test_client):
    """创建提交缺少预期 head 时返回 422，而不是继续提交。"""
    project_id = _register_login_and_create_project(test_client)

    res = test_client.post(
        f"/api/projects/{project_id}/commits",
        json={"message": "commit without expected head"},
    )
    assert res.status_code == 422
    assert "expected_head_commit_required" in res.text


def test_create_commit_with_both_expected_heads_is_rejected(test_client):
    """同时提供两个预期 head 引用（ambiguous）时返回 422。"""
    project_id = _register_login_and_create_project(test_client)

    res = test_client.post(
        f"/api/projects/{project_id}/commits",
        json={
            "message": "commit with both heads",
            "expected_head_commit_id": 1,
            "expected_head_commit_public_id": "some-public-id",
        },
    )
    assert res.status_code == 422


def test_crud_write_rejects_commit_id(test_client):
    """CRUD 写接口携带 commit_id 时必须被显式拒绝（403）。"""
    project_id = _register_login_and_create_project(test_client)

    res = test_client.post(
        f"/api/projects/{project_id}/actors?commit_id=some-commit",
        json={"name": "Should Not Persist"},
    )
    assert res.status_code == 403
    assert "commit_is_read_only" in res.text


def test_generation_confirm_rejects_commit_id(test_client):
    """生成确认（写工作区）携带 commit_id 时必须被显式拒绝（403）。"""
    project_id = _register_login_and_create_project(test_client)

    dummy_draft = SimpleNamespace(
        project_id=project_id,
        draft_id="draft-vc-contract",
        owner_user_id=1,
    )
    app.dependency_overrides[require_owned_generative_draft] = lambda: dummy_draft
    try:
        res = test_client.post(
            f"/api/actor_generation_drafts/{dummy_draft.draft_id}/confirm?commit_id=some-commit",
            json={},
        )
        assert res.status_code == 403
        assert "commit_is_read_only" in res.text
    finally:
        app.dependency_overrides.pop(require_owned_generative_draft, None)


def test_generation_regenerate_rejects_commit_id(test_client):
    """生成草稿"再生成"（mutation）携带 commit_id 时必须被拒绝。"""
    _register_login_and_create_project(test_client)

    dummy_draft = SimpleNamespace(draft_id="draft-regenerate", owner_user_id=1)
    app.dependency_overrides[require_owned_generative_draft] = lambda: dummy_draft
    try:
        res = test_client.post(
            f"/api/actor_generation_drafts/{dummy_draft.draft_id}/regenerate?commit_id=some-commit",
            json={"user_feedback": "more"},
        )
        assert res.status_code == 403
        assert "commit_is_read_only" in res.text
    finally:
        app.dependency_overrides.pop(require_owned_generative_draft, None)


def test_generation_discard_rejects_commit_id(test_client):
    """生成草稿"丢弃"（mutation）携带 commit_id 时必须被拒绝。"""
    _register_login_and_create_project(test_client)

    dummy_draft = SimpleNamespace(draft_id="draft-discard", owner_user_id=1)
    app.dependency_overrides[require_owned_generative_draft] = lambda: dummy_draft
    try:
        res = test_client.delete(
            f"/api/actor_generation_drafts/{dummy_draft.draft_id}?commit_id=some-commit",
        )
        assert res.status_code == 403
        assert "commit_is_read_only" in res.text
    finally:
        app.dependency_overrides.pop(require_owned_generative_draft, None)


def test_crud_write_rejects_commit_id_in_body(test_client):
    """JSON body 中的 commit_id 也必须被拒绝，而不是被 Pydantic 静默忽略。"""
    project_id = _register_login_and_create_project(test_client)

    res = test_client.post(
        f"/api/projects/{project_id}/actors",
        json={"name": "Should Not Persist", "commit_id": "some-commit"},
    )
    assert res.status_code == 403
    assert "commit_is_read_only" in res.text


def test_finding_status_write_rejects_commit_id(test_client):
    """Finding 状态更新（写 FindingOverride）携带 commit_id 时必须被拒绝。"""
    project_id = _register_login_and_create_project(test_client)

    res = test_client.put(
        f"/api/projects/{project_id}/findings/status?commit_id=some-commit",
        json={"findingId": "what:SOME_ISSUE:feature:1", "status": "ignored"},
    )
    assert res.status_code == 403
    assert "commit_is_read_only" in res.text


def test_perception_confirm_rejects_commit_id(test_client):
    """Perception 草稿确认（写需求模型）携带 commit_id 时必须被拒绝。"""
    project_id = _register_login_and_create_project(test_client)

    dummy_draft = SimpleNamespace(project_id=project_id, draft_id="draft-perception", owner_user_id=1)
    app.dependency_overrides[require_owned_generative_draft] = lambda: dummy_draft
    try:
        res = test_client.post(
            f"/api/perception_slot_filling_drafts/{dummy_draft.draft_id}/confirm?commit_id=some-commit",
            json={},
        )
        assert res.status_code == 403
        assert "commit_is_read_only" in res.text
    finally:
        app.dependency_overrides.pop(require_owned_generative_draft, None)


def test_perception_create_rejects_commit_id_in_body(test_client):
    """Perception 草稿创建携带 body commit_id 时必须被拒绝。"""
    project_id = _register_login_and_create_project(test_client)

    res = test_client.post(
        "/api/perception_slot_filling_drafts/actor?branch=main",
        json={
            "project_id": project_id,
            "perception_job_id": 1,
            "commit_id": "some-commit",
        },
    )
    assert res.status_code == 403
    assert "commit_is_read_only" in res.text
