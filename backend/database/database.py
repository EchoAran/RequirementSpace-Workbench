from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

try:
    from .model import Base
except ImportError:
    from model import Base


DATABASE_URL = "sqlite+aiosqlite:///./requirement_space.db"


@event.listens_for(Engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
)


AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_sqlite_schema_migrations)


def _ensure_sqlite_schema_migrations(sync_conn) -> None:
    if sync_conn.dialect.name != "sqlite":
        return

    inspector = inspect(sync_conn)
    if "scenarios" not in inspector.get_table_names():
        return

    scenario_columns = {
        column["name"]
        for column in inspector.get_columns("scenarios")
    }

    if "gherkin_spec_id" not in scenario_columns:
        sync_conn.execute(
            text("ALTER TABLE scenarios ADD COLUMN gherkin_spec_id INTEGER")
        )

    if "gherkin_scenario_index" not in scenario_columns:
        sync_conn.execute(
            text("ALTER TABLE scenarios ADD COLUMN gherkin_scenario_index INTEGER")
        )

    sync_conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_scenarios_gherkin_spec_id "
            "ON scenarios (gherkin_spec_id)"
        )
    )

    if "prototype_previews" in inspector.get_table_names():
        prototype_columns = {
            column["name"]
            for column in inspector.get_columns("prototype_previews")
        }
        if "pages" not in prototype_columns:
            sync_conn.execute(
                text("ALTER TABLE prototype_previews ADD COLUMN pages JSON DEFAULT '[]' NOT NULL")
            )


async def drop_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


if __name__ == "__main__":
    import asyncio

    asyncio.run(init_db())
