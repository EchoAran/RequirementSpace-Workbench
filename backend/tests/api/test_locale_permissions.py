import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database.model import (
    Base,
    UserModel,
    ProjectModel,
    ProjectMemberModel,
    ProjectMemberRole,
    ProjectMemberStatus,
    UserRole,
)
from backend.api.dependencies.project_access import (
    require_project_config_write_access,
    require_project_config_read_access,
)

DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture
async def temp_db():
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield session_factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_project_config_permission_dependencies(temp_db):
    async with temp_db() as session:
        # 1. Create test users
        owner = UserModel(id=2, email="owner@perm.local", password_hash="pwd", role=UserRole.USER.value)
        admin = UserModel(id=3, email="admin@perm.local", password_hash="pwd", role=UserRole.USER.value)
        editor = UserModel(id=4, email="editor@perm.local", password_hash="pwd", role=UserRole.USER.value)
        reviewer = UserModel(id=5, email="reviewer@perm.local", password_hash="pwd", role=UserRole.USER.value)
        viewer = UserModel(id=6, email="viewer@perm.local", password_hash="pwd", role=UserRole.USER.value)
        non_member = UserModel(id=7, email="non@perm.local", password_hash="pwd", role=UserRole.USER.value)
        
        session.add_all([owner, admin, editor, reviewer, viewer, non_member])
        await session.commit()

        # 2. Create project
        # Note: auto_create_project_owner_member listener will run on commit/insert
        # and automatically create the 'owner' membership for user_id = owner.id.
        project = ProjectModel(
            id=10,
            public_id="proj_xyz_123",
            name="Config Permission Test",
            owner_user_id=owner.id
        )
        session.add(project)
        await session.commit()

        # 3. Create project memberships (excluding owner, which is auto-created)
        m_admin = ProjectMemberModel(
            project_id=project.id,
            user_id=admin.id,
            role=ProjectMemberRole.ADMIN.value,
            status=ProjectMemberStatus.ACTIVE.value
        )
        m_editor = ProjectMemberModel(
            project_id=project.id,
            user_id=editor.id,
            role=ProjectMemberRole.EDITOR.value,
            status=ProjectMemberStatus.ACTIVE.value
        )
        m_reviewer = ProjectMemberModel(
            project_id=project.id,
            user_id=reviewer.id,
            role=ProjectMemberRole.REVIEWER.value,
            status=ProjectMemberStatus.ACTIVE.value
        )
        m_viewer = ProjectMemberModel(
            project_id=project.id,
            user_id=viewer.id,
            role=ProjectMemberRole.VIEWER.value,
            status=ProjectMemberStatus.ACTIVE.value
        )
        session.add_all([m_admin, m_editor, m_reviewer, m_viewer])
        await session.commit()

    # Create fresh session for tests
    async with temp_db() as session:
        # Helper to refresh instances in new session
        async def fetch_user(uid):
            return await session.get(UserModel, uid)

        owner_user = await fetch_user(2)
        admin_user = await fetch_user(3)
        editor_user = await fetch_user(4)
        reviewer_user = await fetch_user(5)
        viewer_user = await fetch_user(6)
        non_member_user = await fetch_user(7)

        project_public_id = "proj_xyz_123"

        # -------------------------------------------------------------
        # Test Owner Access: Read (OK), Write (OK)
        # -------------------------------------------------------------
        res_read = await require_project_config_read_access(project_public_id, owner_user, session)
        assert res_read.id == 10

        res_write = await require_project_config_write_access(project_public_id, owner_user, session)
        assert res_write.id == 10

        # -------------------------------------------------------------
        # Test Admin Access: Read (OK), Write (OK)
        # -------------------------------------------------------------
        res_read = await require_project_config_read_access(project_public_id, admin_user, session)
        assert res_read.id == 10

        res_write = await require_project_config_write_access(project_public_id, admin_user, session)
        assert res_write.id == 10

        # -------------------------------------------------------------
        # Test Editor Access: Read (OK), Write (Forbidden - 403)
        # -------------------------------------------------------------
        res_read = await require_project_config_read_access(project_public_id, editor_user, session)
        assert res_read.id == 10

        with pytest.raises(HTTPException) as exc_info:
            await require_project_config_write_access(project_public_id, editor_user, session)
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "insufficient_project_role"

        # -------------------------------------------------------------
        # Test Reviewer Access: Read (OK), Write (Forbidden - 403)
        # -------------------------------------------------------------
        res_read = await require_project_config_read_access(project_public_id, reviewer_user, session)
        assert res_read.id == 10

        with pytest.raises(HTTPException) as exc_info:
            await require_project_config_write_access(project_public_id, reviewer_user, session)
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "insufficient_project_role"

        # -------------------------------------------------------------
        # Test Viewer Access: Read (OK), Write (Forbidden - 403)
        # -------------------------------------------------------------
        res_read = await require_project_config_read_access(project_public_id, viewer_user, session)
        assert res_read.id == 10

        with pytest.raises(HTTPException) as exc_info:
            await require_project_config_write_access(project_public_id, viewer_user, session)
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "insufficient_project_role"

        # -------------------------------------------------------------
        # Test Non-Member Access: Read (Not Found - 404), Write (Not Found - 404)
        # -------------------------------------------------------------
        with pytest.raises(HTTPException) as exc_info:
            await require_project_config_read_access(project_public_id, non_member_user, session)
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "project_not_found"

        with pytest.raises(HTTPException) as exc_info:
            await require_project_config_write_access(project_public_id, non_member_user, session)
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "project_not_found"

