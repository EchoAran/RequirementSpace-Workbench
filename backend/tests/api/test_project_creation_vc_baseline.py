"""
Integration tests for immediate version control baseline initialization on project creation
and role permission boundaries for branch creation and workspace modifications.
"""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.modules.version_control.public import resolve_branch_context
from backend.database.database import Base, get_session
from backend.database.model import (
    GenerativeDraftModel,
    ProjectMemberModel,
    ProjectMemberStatus,
    ProjectModel,
)
from backend.main import app

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def vc_test_db():
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
    yield session_factory
    app.dependency_overrides.pop(get_session, None)
    await engine.dispose()


def _register_user(client: TestClient, email: str, password: str = "password123") -> tuple[int, str]:
    res = client.post("/api/auth/register", json={"email": email, "password": password})
    assert res.status_code == 200
    user_id = int(res.json()["id"])
    cookie = client.cookies.get("auth_session")
    return user_id, cookie


@pytest.mark.asyncio
async def test_blank_project_creation_initializes_vc_immediately(vc_test_db):
    """验证创建空白项目后无需重启，立即能查询到一个 baseline、一个受保护 main 和对应 workspace。"""
    client = TestClient(app)
    _user_id, _cookie = _register_user(client, "owner_blank@test.com")

    # 1. 创建空白项目
    res = client.post(
        "/api/blank_projects",
        json={
            "user_requirements": "Building a collaborative requirement workbench",
            "project_name": "Instant VC Project",
            "project_description": "Project with immediate VC initialization",
        },
    )
    assert res.status_code == 200
    data = res.json()
    project_public_id = data["projectId"]

    # 2. 立即查询分支列表
    branches_res = client.get(f"/api/projects/{project_public_id}/branches")
    assert branches_res.status_code == 200
    branches = branches_res.json()
    assert len(branches) == 1

    main_branch = branches[0]
    assert main_branch["name"] == "main"
    assert main_branch["is_protected"] is True
    assert main_branch["is_default"] is True
    assert main_branch["head_commit_id"] is not None
    assert main_branch["head_commit_public_id"] is not None
    assert main_branch["permissions"]["can_write"] is False  # main is protected

    # 3. 立即查询 Commit 列表
    commits_res = client.get(f"/api/projects/{project_public_id}/commits")
    assert commits_res.status_code == 200
    commits = commits_res.json()
    assert len(commits["commits"]) == 1
    baseline_commit = commits["commits"][0]
    assert "Initial baseline commit" in baseline_commit["message"]


@pytest.mark.asyncio
async def test_project_draft_confirm_initializes_vc_immediately(vc_test_db):
    """验证确认 AI 项目草稿后，同一事务内建立基线 Commit、main 分支与 BranchWorkspace。"""
    client = TestClient(app)
    user_id, _cookie = _register_user(client, "owner_draft@test.com")

    draft_payload = {
        "user_requirements": "E-commerce platform checkout flow",
        "project_preview": {
            "project_name": "E-Commerce Checkout",
            "project_description": "Checkout process",
        },
        "actors": [
            {"actor_name": "Shopper", "actor_description": "Buys items", "actor_number": "A001"},
        ],
        "features": [
            {
                "feature_name": "Checkout Flow",
                "feature_description": "Checkout",
                "feature_number": "F001",
                "actor_numbers": ["A001"],
            }
        ],
    }

    draft_id = str(uuid.uuid4())

    async with vc_test_db() as session:
        draft_model = GenerativeDraftModel(
            draft_id=draft_id,
            draft_type="project_creation",
            payload=draft_payload,
            owner_user_id=user_id,
        )
        session.add(draft_model)
        await session.commit()

    # 确认草稿
    confirm_res = client.post(f"/api/project_creation_drafts/{draft_id}/confirm")
    assert confirm_res.status_code == 200
    project_public_id = confirm_res.json()["projectId"]

    # 验证分支与基线
    branches_res = client.get(f"/api/projects/{project_public_id}/branches")
    assert branches_res.status_code == 200
    branches = branches_res.json()
    assert len(branches) == 1
    assert branches[0]["name"] == "main"
    assert branches[0]["head_commit_public_id"] is not None

    commits_res = client.get(f"/api/projects/{project_public_id}/commits")
    assert commits_res.status_code == 200
    commits = commits_res.json()["commits"]
    assert len(commits) == 1
    assert commits[0]["summary"]["actor_count"] == 1
    assert commits[0]["summary"]["feature_count"] == 1


@pytest.mark.asyncio
async def test_viewer_and_reviewer_cannot_create_branch_or_gain_write_permissions(vc_test_db):
    """
    验证权限隔离：
    1. owner / editor 可以创建分支 (201)
    2. reviewer / viewer 尝试创建分支被拒绝 (403)
    3. 如果存在低权限用户的历史分支，resolve_branch_context 判权仍为 can_write=False
    """
    client_owner = TestClient(app)
    _owner_id, _ = _register_user(client_owner, "owner_roles@test.com")

    client_editor = TestClient(app)
    editor_id, _ = _register_user(client_editor, "editor_roles@test.com")

    client_reviewer = TestClient(app)
    reviewer_id, _ = _register_user(client_reviewer, "reviewer_roles@test.com")

    client_viewer = TestClient(app)
    viewer_id, _ = _register_user(client_viewer, "viewer_roles@test.com")

    # 1. Owner 创建项目
    res = client_owner.post(
        "/api/blank_projects",
        json={
            "user_requirements": "Test roles project",
            "project_name": "Roles Project",
            "project_description": "Description",
        },
    )
    assert res.status_code == 200
    project_public_id = res.json()["projectId"]

    async with vc_test_db() as session:
        proj_query = await session.execute(
            select(ProjectModel).where(ProjectModel.public_id == project_public_id)
        )
        proj = proj_query.scalar_one()
        proj_id = proj.id
        session.add_all([
            ProjectMemberModel(project_id=proj.id, user_id=editor_id, role="editor", status=ProjectMemberStatus.ACTIVE.value),
            ProjectMemberModel(project_id=proj.id, user_id=reviewer_id, role="reviewer", status=ProjectMemberStatus.ACTIVE.value),
            ProjectMemberModel(project_id=proj.id, user_id=viewer_id, role="viewer", status=ProjectMemberStatus.ACTIVE.value),
        ])
        await session.commit()

    # 2. Editor 创建分支 -> 应该成功 (201)
    editor_branch_res = client_editor.post(
        f"/api/projects/{project_public_id}/branches",
        json={"name": "feature/editor-work", "description": "editor branch"},
    )
    assert editor_branch_res.status_code == 201
    editor_branch = editor_branch_res.json()
    assert editor_branch["permissions"]["can_write"] is True

    # 3. Reviewer 尝试创建分支 -> 应该返回 403
    reviewer_branch_res = client_reviewer.post(
        f"/api/projects/{project_public_id}/branches",
        json={"name": "feature/reviewer-work", "description": "reviewer branch"},
    )
    assert reviewer_branch_res.status_code == 403

    # 4. Viewer 尝试创建分支 -> 应该返回 403
    viewer_branch_res = client_viewer.post(
        f"/api/projects/{project_public_id}/branches",
        json={"name": "feature/viewer-work", "description": "viewer branch"},
    )
    assert viewer_branch_res.status_code == 403

    # 5. 验证已存在分支对 Viewer/Reviewer 只读
    b_detail_res = client_reviewer.get(
        f"/api/projects/{project_public_id}/branches/{editor_branch['public_id']}"
    )
    assert b_detail_res.status_code == 200
    assert b_detail_res.json()["permissions"]["can_write"] is False

    # 6. 验证在分支上下文判定时 viewer 用户访问非 main 分支，resolve_branch_context 仍严格判定 can_write=False
    async with vc_test_db() as session:
        _branch_obj, _ws_obj, perms = await session.run_sync(
            lambda s: resolve_branch_context(
                s,
                project_id=proj_id,
                branch_ref=editor_branch["public_id"],
                user_id=viewer_id,
            )
        )
    assert perms["can_write"] is False
