import os
import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Set encryption key before importing model/database
from cryptography.fernet import Fernet
if "LLM_CONFIG_ENCRYPTION_KEY" not in os.environ:
    os.environ["LLM_CONFIG_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

from backend.database.model import Base, UserModel, ProjectModel, GenerativeDraftModel, UserLLMConfigModel, UserRole


@pytest.mark.asyncio
async def test_schema_bootstrap_from_metadata(tmp_path):
    db_file = tmp_path / "test_bootstrap.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"

    # Create engine for this temp database
    temp_engine = create_async_engine(db_url, echo=False)

    # Run bootstrap
    async with temp_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Verify tables exist
    def verify_tables(sync_conn):
        inspector = inspect(sync_conn)
        tables = inspector.get_table_names()
        assert "users" in tables
        assert "user_llm_configs" in tables
        assert "auth_sessions" in tables
        assert "projects" in tables
        assert "generative_drafts" in tables

        # Verify nullable=False constraints on owner_user_id
        proj_cols = {c["name"]: c for c in inspector.get_columns("projects")}
        assert proj_cols["owner_user_id"]["nullable"] is False

        draft_cols = {c["name"]: c for c in inspector.get_columns("generative_drafts")}
        assert draft_cols["owner_user_id"]["nullable"] is False

    async with temp_engine.connect() as conn:
        await conn.run_sync(verify_tables)

    await temp_engine.dispose()
    import logging
    print("BOOTSTRAP TEST END ROOT ID:", id(logging.getLogger()), flush=True)


@pytest.mark.asyncio
async def test_schema_cascade_deletion(tmp_path):
    db_file = tmp_path / "test_cascade.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"

    temp_engine = create_async_engine(db_url, echo=False)

    # Bootstrap
    async with temp_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(
        temp_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        # Create user
        user = UserModel(
            email="test@example.com",
            password_hash="fake_hash",
            role=UserRole.USER.value
        )
        session.add(user)
        await session.commit()

        # Create user LLM config
        llm_config = UserLLMConfigModel(
            user_id=user.id,
            api_url="http://localhost",
            encrypted_api_key="enc_key",
            api_key_last4="1234",
            model_name="test-model"
        )
        session.add(llm_config)

        # Create project owned by user
        project = ProjectModel(
            owner_user_id=user.id,
            name="Test Project"
        )
        session.add(project)

        # Create draft owned by user
        draft = GenerativeDraftModel(
            owner_user_id=user.id,
            draft_id="draft123",
            draft_type="actor",
            payload={}
        )
        session.add(draft)
        await session.commit()

        # Check they exist
        db_user = await session.get(UserModel, user.id)
        assert db_user is not None

        # Delete user
        await session.delete(db_user)
        await session.commit()

        # Verify cascade deletes everything
        from sqlalchemy import select
        db_config = await session.execute(select(UserLLMConfigModel).where(UserLLMConfigModel.user_id == user.id))
        assert db_config.scalar() is None

        db_project = await session.execute(select(ProjectModel).where(ProjectModel.owner_user_id == user.id))
        assert db_project.scalar() is None

        db_draft = await session.execute(select(GenerativeDraftModel).where(GenerativeDraftModel.owner_user_id == user.id))
        assert db_draft.scalar() is None

    await temp_engine.dispose()


def test_postgresql_ddl_compilation():
    """Verify that SQLAlchemy metadata can be compiled successfully under PostgreSQL dialect without any syntax/type conflicts."""
    from sqlalchemy import create_mock_engine

    statements = []
    def executor(sql, *multiparams, **params):
        statements.append(str(sql.compile(dialect=engine.dialect)))

    engine = create_mock_engine("postgresql://", executor)
    Base.metadata.create_all(engine)

    assert len(statements) > 0
    ddl_str = "\n".join(statements)
    
    # Assert key tables exist
    assert "CREATE TABLE users" in ddl_str
    assert "CREATE TABLE user_llm_configs" in ddl_str
    assert "CREATE TABLE auth_sessions" in ddl_str
    assert "CREATE TABLE projects" in ddl_str
    assert "CREATE TABLE generative_drafts" in ddl_str

    # Assert non-nullable owner constraints on postgres DDL
    # In PostgreSQL, it will compile to e.g. "owner_user_id INTEGER NOT NULL"
    assert "owner_user_id INTEGER NOT NULL" in ddl_str


@pytest.mark.asyncio
async def test_postgresql_schema_bootstrap_actual():
    """If TEST_POSTGRES_URL is configured, connect to the real PostgreSQL db,
    drop existing tables, run create_all(), and verify constraints.
    """
    pg_url = os.getenv("TEST_POSTGRES_URL")
    if not pg_url:
        pytest.skip("TEST_POSTGRES_URL environment variable is not set. Skipping real PostgreSQL integration test.")

    # In case the URL is sync, convert/check for asyncpg or handle appropriately.
    # Note: SQLAlchemy async engine needs +asyncpg.
    if pg_url.startswith("postgresql://"):
        pg_url = pg_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    pg_engine = create_async_engine(pg_url, echo=False)

    try:
        # Drop all tables first to ensure we start from an empty database
        async with pg_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        # Verify tables and constraints
        def verify_pg_tables(sync_conn):
            inspector = inspect(sync_conn)
            tables = inspector.get_table_names()
            assert "users" in tables
            assert "user_llm_configs" in tables
            assert "auth_sessions" in tables
            assert "projects" in tables
            assert "generative_drafts" in tables

            # Verify nullable=False constraints on owner_user_id
            proj_cols = {c["name"]: c for c in inspector.get_columns("projects")}
            assert proj_cols["owner_user_id"]["nullable"] is False

            draft_cols = {c["name"]: c for c in inspector.get_columns("generative_drafts")}
            assert draft_cols["owner_user_id"]["nullable"] is False

        async with pg_engine.connect() as conn:
            await conn.run_sync(verify_pg_tables)
            
    finally:
        # Clean up by dropping all tables
        async with pg_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await pg_engine.dispose()


