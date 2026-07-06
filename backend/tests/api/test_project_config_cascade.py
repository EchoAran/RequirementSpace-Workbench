"""
Phase 6 - 验收测试：项目删除时级联清理 strategy config

验收标准（来自 docs/implementation_plan/.../06_rollout_testing_and_acceptance.md 第 9 条）：
  project_generation_strategy_configs.project_id 唯一约束和项目删除级联清理测试。
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import select

from backend.main import app
from backend.database.model import (
    Base,
    ProjectModel,
    UserModel,
    ProjectGenerationStrategyConfigModel,
)
from backend.database.database import get_session

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_db():
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


def register_user(client, email, password):
    res = client.post(
        "/api/auth/register",
        json={"email": email, "password": password}
    )
    assert res.status_code == 200
    res_login = client.post(
        "/api/auth/login",
        json={"email": email, "password": password}
    )
    assert res_login.status_code == 200
    return res_login.json()["id"], res_login.cookies.get("auth_session")


@pytest.mark.asyncio
async def test_project_deletion_cascades_strategy_config(test_db):
    """
    验收：删除项目后 project_generation_strategy_configs 记录应被级联删除。

    流程：
    1. 创建项目并保存自定义策略配置
    2. 确认策略配置存在
    3. 删除项目
    4. 验证策略配置记录已从数据库中清除
    """
    client = TestClient(app)

    owner_id, owner_cookie = register_user(client, "cascade_owner@test.com", "password123")

    # 1. Create project
    async with test_db() as session:
        project = ProjectModel(
            name="Cascade Test Project",
            owner_user_id=owner_id,
            user_requirements="Test cascade delete.",
        )
        session.add(project)
        await session.commit()
        project_public_id = project.public_id
        project_db_id = project.id

    client.cookies.set("auth_session", owner_cookie)

    # 2. Save custom strategy configuration for the project
    valid_payload = {
        "enabled": True,
        "candidate_count": 2,
        "strategies": [
            {
                "id": "balanced",
                "label": "均衡版",
                "description": "均衡生成策略",
                "instruction": "This is a valid instruction text with more than twenty characters.",
                "generation_types": ["actor"],
                "enabled": True,
                "order": 0
            },
            {
                "id": "comprehensive",
                "label": "全面版",
                "description": "全面生成策略",
                "instruction": "This is another valid instruction text with more than twenty characters.",
                "generation_types": ["actor"],
                "enabled": True,
                "order": 1
            }
        ]
    }
    res_put = client.put(
        f"/api/projects/{project_public_id}/configuration/generation-strategies",
        json=valid_payload,
    )
    assert res_put.status_code == 200, f"Unexpected: {res_put.text}"

    # 3. Verify strategy config exists in DB
    async with test_db() as session:
        stmt = select(ProjectGenerationStrategyConfigModel).where(
            ProjectGenerationStrategyConfigModel.project_id == project_db_id
        )
        config = (await session.execute(stmt)).scalar_one_or_none()
        assert config is not None, "Strategy config should exist before project deletion"
        assert config.candidate_count == 2

    # 4. Delete the project via API
    res_del = client.delete(f"/api/projects/{project_public_id}")
    assert res_del.status_code == 200, f"Delete project failed: {res_del.text}"
    assert res_del.json().get("message") == "project_deleted"

    # 5. Verify strategy config was cascade-deleted
    async with test_db() as session:
        stmt_after = select(ProjectGenerationStrategyConfigModel).where(
            ProjectGenerationStrategyConfigModel.project_id == project_db_id
        )
        orphan = (await session.execute(stmt_after)).scalar_one_or_none()
        assert orphan is None, (
            "ProjectGenerationStrategyConfigModel should have been cascade-deleted "
            "when the parent project was deleted."
        )


@pytest.mark.asyncio
async def test_project_id_unique_constraint(test_db):
    """
    验收：project_id 列有唯一约束，同一项目不能保存两条策略配置记录。

    实现上通过 upsert（save_for_project），业务层保证唯一性。
    此测试直接在 DB 层验证唯一约束存在：尝试直接插入重复 project_id 应报错。
    """
    from sqlalchemy.exc import IntegrityError

    async with test_db() as session:
        owner = UserModel(
            email="unique_owner@test.com",
            password_hash="test-hash",
        )
        session.add(owner)
        await session.flush()

        project = ProjectModel(
            name="Unique Constraint Test Project",
            owner_user_id=owner.id,
            user_requirements="Unique constraint check.",
        )
        session.add(project)
        await session.flush()
        project_db_id = project.id

        # Insert first config
        config1 = ProjectGenerationStrategyConfigModel(
            project_id=project_db_id,
            enabled=True,
            candidate_count=2,
            strategies=[],
        )
        session.add(config1)
        await session.flush()

        # Attempt to insert duplicate — should raise IntegrityError
        config2 = ProjectGenerationStrategyConfigModel(
            project_id=project_db_id,
            enabled=False,
            candidate_count=1,
            strategies=[],
        )
        session.add(config2)

        with pytest.raises(IntegrityError):
            await session.flush()
