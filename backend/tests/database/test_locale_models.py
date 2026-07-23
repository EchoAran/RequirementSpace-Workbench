import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from backend.database.model import Base, UserModel, ProjectModel, UserRole

@pytest.mark.asyncio
async def test_locale_columns_exist_and_metadata(tmp_path):
    db_file = tmp_path / "test_locale_meta.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"

    temp_engine = create_async_engine(db_url, echo=False)

    async with temp_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    def verify_columns(sync_conn):
        inspector = inspect(sync_conn)
        
        # Verify preferred_locale in users
        user_cols = {c["name"]: c for c in inspector.get_columns("users")}
        assert "preferred_locale" in user_cols
        assert user_cols["preferred_locale"]["nullable"] is False
        
        # Verify content_locale in projects
        proj_cols = {c["name"]: c for c in inspector.get_columns("projects")}
        assert "content_locale" in proj_cols
        assert proj_cols["content_locale"]["nullable"] is True

    async with temp_engine.connect() as conn:
        await conn.run_sync(verify_columns)

    await temp_engine.dispose()


@pytest.mark.asyncio
async def test_locale_default_values(tmp_path):
    db_file = tmp_path / "test_locale_defaults.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"

    temp_engine = create_async_engine(db_url, echo=False)

    async with temp_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(
        temp_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        # Create user without explicit preferred_locale
        user = UserModel(
            email="locale_test@example.com",
            password_hash="fake_hash",
            role=UserRole.USER.value
        )
        session.add(user)
        await session.commit()

        # Create project without explicit content_locale
        project = ProjectModel(
            owner_user_id=user.id,
            name="Locale Test Project"
        )
        session.add(project)
        await session.commit()

        # Query and assert defaults
        assert user.preferred_locale == "zh-CN"
        assert project.content_locale is None

    await temp_engine.dispose()


@pytest.mark.asyncio
async def test_locale_python_validation(tmp_path):
    db_file = tmp_path / "test_locale_val.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    temp_engine = create_async_engine(db_url, echo=False)
    async with temp_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(
        temp_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        user = UserModel(
            email="val_test@example.com",
            password_hash="fake_hash",
            role=UserRole.USER.value
        )
        # Setting invalid preferred_locale should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            user.preferred_locale = "invalid_locale"
        assert "Invalid preferred_locale" in str(exc_info.value)

        project = ProjectModel(
            owner_user_id=1,
            name="Val Test Project"
        )
        # Setting invalid content_locale should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            project.content_locale = "invalid_locale"
        assert "Invalid content_locale" in str(exc_info.value)

    await temp_engine.dispose()


@pytest.mark.asyncio
async def test_locale_db_constraints(tmp_path):
    db_file = tmp_path / "test_locale_const.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    temp_engine = create_async_engine(db_url, echo=False)
    async with temp_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(
        temp_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        from sqlalchemy import text
        from sqlalchemy.exc import IntegrityError

        # Raw INSERT bypassing SQLAlchemy validates decorator to test DB CheckConstraint
        # For preferred_locale:
        with pytest.raises(IntegrityError):
            await session.execute(
                text("INSERT INTO users (email, password_hash, role, is_active, created_at, updated_at, preferred_locale) "
                     "VALUES ('db_val_user@example.com', 'fake_hash', 'user', 1, '2026-07-13 00:00:00', '2026-07-13 00:00:00', 'invalid')")
            )
            await session.commit()
            
        await session.rollback()

        # For content_locale:
        # First insert a valid user so foreign key constraint passes
        await session.execute(
            text("INSERT INTO users (id, email, password_hash, role, is_active, created_at, updated_at, preferred_locale) "
                 "VALUES (999, 'db_val_user_ok@example.com', 'fake_hash', 'user', 1, '2026-07-13 00:00:00', '2026-07-13 00:00:00', 'zh-CN')")
        )
        await session.commit()

        with pytest.raises(IntegrityError):
            await session.execute(
                text("INSERT INTO projects (public_id, owner_user_id, name, description, user_requirements, kano_status, unlocked_stages, created_at, updated_at, content_locale) "
                     "VALUES ('p1234567', 999, 'Test Project', '', '', 'missing', '', '2026-07-13 00:00:00', '2026-07-13 00:00:00', 'invalid')")
            )
            await session.commit()

    await temp_engine.dispose()

