"""
Phase 3 Contract Tests for Commit Read-Only & Expected-Head Constraints.

覆盖两项 P1 验收：
1. 创建提交必须携带预期 head（缺失时 422）。
2. 需求模型写接口携带 commit_id 时必须被显式拒绝（403），而不是被静默忽略后写入当前工作区。
"""
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import app
from backend.database.database import get_session, Base
from backend.database.model import (
    ProjectModel,
    UserModel,
    RequirementBranchModel,
    RequirementCommitModel,
)
from backend.api.dependencies.ownership import require_owned_generative_draft

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


def _register_login_and_create_project(client):
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
    project_id = res.json()["project_id"]
    client.put(
        "/api/account/llm-config",
        json={
            "api_url": "https://api.openai.com/v1",
            "api_key": "sk-dummy-test-key-string-long-enough",
            "model_name": "gpt-4-turbo",
        },
    )
    return project_id


def test_create_commit_without_expected_head_is_rejected():
    """创建提交缺少预期 head 时返回 422，而不是继续提交。"""
    client = TestClient(app)
    project_id = _register_login_and_create_project(client)

    res = client.post(
        f"/api/projects/{project_id}/commits",
        json={"message": "commit without expected head"},
    )
    assert res.status_code == 422
    assert "expected_head_commit_required" in res.text


def test_create_commit_with_both_expected_heads_is_rejected():
    """同时提供两个预期 head 引用（ambiguous）时返回 422。"""
    client = TestClient(app)
    project_id = _register_login_and_create_project(client)

    res = client.post(
        f"/api/projects/{project_id}/commits",
        json={
            "message": "commit with both heads",
            "expected_head_commit_id": 1,
            "expected_head_commit_public_id": "some-public-id",
        },
    )
    assert res.status_code == 422


def test_crud_write_rejects_commit_id():
    """CRUD 写接口携带 commit_id 时必须被显式拒绝（403）。"""
    client = TestClient(app)
    project_id = _register_login_and_create_project(client)

    res = client.post(
        f"/api/projects/{project_id}/actors?commit_id=some-commit",
        json={"name": "Should Not Persist"},
    )
    assert res.status_code == 403
    assert "commit_is_read_only" in res.text


def test_generation_confirm_rejects_commit_id():
    """生成确认（写工作区）携带 commit_id 时必须被显式拒绝（403）。"""
    client = TestClient(app)
    project_id = _register_login_and_create_project(client)

    dummy_draft = SimpleNamespace(
        project_id=project_id,
        draft_id="draft-vc-contract",
        owner_user_id=1,
    )
    app.dependency_overrides[require_owned_generative_draft] = lambda: dummy_draft
    try:
        res = client.post(
            f"/api/actor_generation_drafts/{dummy_draft.draft_id}/confirm?commit_id=some-commit",
            json={},
        )
        assert res.status_code == 403
        assert "commit_is_read_only" in res.text
    finally:
        app.dependency_overrides.pop(require_owned_generative_draft, None)


def test_generation_regenerate_rejects_commit_id():
    """生成草稿"再生成"（mutation）携带 commit_id 时必须被拒绝。"""
    client = TestClient(app)
    project_id = _register_login_and_create_project(client)

    dummy_draft = SimpleNamespace(draft_id="draft-regenerate", owner_user_id=1)
    app.dependency_overrides[require_owned_generative_draft] = lambda: dummy_draft
    try:
        res = client.post(
            f"/api/actor_generation_drafts/{dummy_draft.draft_id}/regenerate?commit_id=some-commit",
            json={"user_feedback": "more"},
        )
        assert res.status_code == 403
        assert "commit_is_read_only" in res.text
    finally:
        app.dependency_overrides.pop(require_owned_generative_draft, None)


def test_generation_discard_rejects_commit_id():
    """生成草稿"丢弃"（mutation）携带 commit_id 时必须被拒绝。"""
    client = TestClient(app)
    project_id = _register_login_and_create_project(client)

    dummy_draft = SimpleNamespace(draft_id="draft-discard", owner_user_id=1)
    app.dependency_overrides[require_owned_generative_draft] = lambda: dummy_draft
    try:
        res = client.delete(
            f"/api/actor_generation_drafts/{dummy_draft.draft_id}?commit_id=some-commit",
        )
        assert res.status_code == 403
        assert "commit_is_read_only" in res.text
    finally:
        app.dependency_overrides.pop(require_owned_generative_draft, None)


def test_crud_write_rejects_commit_id_in_body():
    """JSON body 中的 commit_id 也必须被拒绝，而不是被 Pydantic 静默忽略。"""
    client = TestClient(app)
    project_id = _register_login_and_create_project(client)

    res = client.post(
        f"/api/projects/{project_id}/actors",
        json={"name": "Should Not Persist", "commit_id": "some-commit"},
    )
    assert res.status_code == 403
    assert "commit_is_read_only" in res.text


def test_finding_status_write_rejects_commit_id():
    """Finding 状态更新（写 FindingOverride）携带 commit_id 时必须被拒绝。"""
    client = TestClient(app)
    project_id = _register_login_and_create_project(client)

    res = client.put(
        f"/api/projects/{project_id}/findings/status?commit_id=some-commit",
        json={"findingId": "what:SOME_ISSUE:feature:1", "status": "ignored"},
    )
    assert res.status_code == 403
    assert "commit_is_read_only" in res.text


def test_perception_confirm_rejects_commit_id():
    """Perception 草稿确认（写需求模型）携带 commit_id 时必须被拒绝。"""
    client = TestClient(app)
    project_id = _register_login_and_create_project(client)

    dummy_draft = SimpleNamespace(project_id=project_id, draft_id="draft-perception", owner_user_id=1)
    app.dependency_overrides[require_owned_generative_draft] = lambda: dummy_draft
    try:
        res = client.post(
            f"/api/perception_slot_filling_drafts/{dummy_draft.draft_id}/confirm?commit_id=some-commit",
            json={},
        )
        assert res.status_code == 403
        assert "commit_is_read_only" in res.text
    finally:
        app.dependency_overrides.pop(require_owned_generative_draft, None)


def test_perception_create_rejects_commit_id_in_body():
    """Perception 草稿创建携带 body commit_id 时必须被拒绝。"""
    client = TestClient(app)
    project_id = _register_login_and_create_project(client)

    res = client.post(
        f"/api/perception_slot_filling_drafts/actor?branch=main",
        json={
            "project_id": project_id,
            "perception_job_id": 1,
            "commit_id": "some-commit",
        },
    )
    assert res.status_code == 403
    assert "commit_is_read_only" in res.text
