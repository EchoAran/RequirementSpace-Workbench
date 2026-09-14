from __future__ import annotations

import logging
import time
from collections.abc import AsyncGenerator

from sqlalchemy import event
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


import os
import urllib.parse

from backend.core.config import DATABASE_URL as raw_db_url
from backend.core.logging import get_logger, log_event, sanitize_database_url, sanitize_message
from backend.core.logging.events import (
    DB_BOOTSTRAP_COMPLETED,
    DB_BOOTSTRAP_FAILED,
    DB_BOOTSTRAP_STARTED,
    DB_CONNECTION_URL_NORMALIZED,
    DB_INIT_COMPLETED,
    DB_INIT_FAILED,
    DB_INIT_STARTED,
    DB_STAMP_COMPLETED,
    DB_STAMP_FAILED,
    DB_STAMP_STARTED,
)

logger = get_logger("backend.database")


def _db_engine_name(db_url: str) -> str:
    if "sqlite" in db_url:
        return "sqlite"
    if db_url.startswith(("postgresql", "postgres")):
        return "postgresql"
    return "unknown"


def _sync_migration_url(db_url: str) -> str:
    if db_url.startswith("sqlite+aiosqlite://"):
        return db_url.replace("sqlite+aiosqlite://", "sqlite://")
    if db_url.startswith("postgresql+asyncpg://"):
        return db_url.replace("postgresql+asyncpg://", "postgresql://")
    if db_url.startswith("postgres://"):
        return db_url.replace("postgres://", "postgresql://")
    return db_url


def _log_db_event(
    level: int,
    event: str,
    message: str,
    **fields: object,
) -> None:
    log_event(logger, level, "db", event, message, **fields)

if raw_db_url.startswith("postgresql://") or raw_db_url.startswith("postgres://"):
    # Translate scheme to postgresql+asyncpg
    scheme = "postgresql+asyncpg"
    rest = raw_db_url.split("://", 1)[1]

    # Automatically strip '-pooler' from Neon connection strings to avoid transaction pooler errors on Alembic migrations
    if "-pooler" in rest:
        rest = rest.replace("-pooler", "")
        _log_db_event(
            logging.INFO,
            DB_CONNECTION_URL_NORMALIZED,
            "Database connection URL normalized for migration compatibility",
            db_engine="postgresql",
            database_url=sanitize_database_url(raw_db_url),
            normalization="strip_neon_pooler",
        )

    # Use dummy scheme http to let urlparse extract netloc correctly
    parsed = urllib.parse.urlparse(f"http://{rest}")

    # Strip 'sslmode' and 'channel_binding' as asyncpg does not support them and throws TypeError
    query_params = urllib.parse.parse_qs(parsed.query)
    query_params.pop("sslmode", None)
    query_params.pop("channel_binding", None)
    new_query = urllib.parse.urlencode(query_params, doseq=True)

    DATABASE_URL = f"{scheme}://{parsed.netloc}{parsed.path}"
    if new_query:
        DATABASE_URL += f"?{new_query}"

    engine: AsyncEngine = create_async_engine(
        DATABASE_URL,
        echo=False,
        future=True,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args={"ssl": True, "timeout": 5}
    )
else:
    DATABASE_URL = raw_db_url
    engine: AsyncEngine = create_async_engine(
        DATABASE_URL,
        echo=False,
        future=True,
        pool_pre_ping=True,
    )


@event.listens_for(Engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
    # Only run SQLite PRAGMAs on real sqlite connections
    conn_module = type(dbapi_connection).__module__.lower()
    conn_class = type(dbapi_connection).__name__.lower()
    if "sqlite" in conn_module or "sqlite" in conn_class:
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()
        except Exception:
            pass


AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
)


def run_stamp_head() -> None:
    """Stamp Alembic to head to mark schema as up to date after metadata create_all."""
    from pathlib import Path

    from alembic.config import Config

    from alembic import command

    started = time.perf_counter()
    _log_db_event(
        logging.INFO,
        DB_STAMP_STARTED,
        "Database Alembic stamp started",
        alembic_target="head",
    )
    base_dir = Path(__file__).resolve().parents[2]
    db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./requirement_space.db").strip("'\" ")
    if "-pooler" in db_url:
        db_url = db_url.replace("-pooler", "")

    if "?" in db_url:
        import urllib.parse
        base_part, query_part = db_url.split("?", 1)
        params = urllib.parse.parse_qs(query_part)
        params.pop("sslmode", None)
        params.pop("channel_binding", None)
        new_query = urllib.parse.urlencode(params, doseq=True)
        db_url = f"{base_part}?{new_query}" if new_query else base_part

    alembic_ini_path = base_dir / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("script_location", str(base_dir / "alembic"))

    alembic_url = _sync_migration_url(db_url)

    alembic_cfg.set_main_option("sqlalchemy.url", alembic_url)

    try:
        command.stamp(alembic_cfg, "head")
    except Exception as e:
        _log_db_event(
            logging.ERROR,
            DB_STAMP_FAILED,
            "Database Alembic stamp failed",
            db_engine=_db_engine_name(db_url),
            database_url=sanitize_database_url(db_url),
            alembic_target="head",
            duration_ms=int((time.perf_counter() - started) * 1000),
            error_type=type(e).__name__,
            error_message=sanitize_message(str(e)),
        )
        raise e
    else:
        _log_db_event(
            logging.INFO,
            DB_STAMP_COMPLETED,
            "Database Alembic stamp completed",
            db_engine=_db_engine_name(db_url),
            alembic_target="head",
            duration_ms=int((time.perf_counter() - started) * 1000),
        )


async def bootstrap_db() -> None:
    """Bootstrap database schema directly from metadata."""
    started = time.perf_counter()
    _log_db_event(
        logging.INFO,
        DB_BOOTSTRAP_STARTED,
        "Database bootstrap started",
        db_engine=_db_engine_name(DATABASE_URL),
    )
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Stamp Alembic to head to mark database as migrated (makes future runs idempotent)
        import asyncio
        await asyncio.to_thread(run_stamp_head)
    except Exception as exc:
        _log_db_event(
            logging.ERROR,
            DB_BOOTSTRAP_FAILED,
            "Database bootstrap failed",
            db_engine=_db_engine_name(DATABASE_URL),
            duration_ms=int((time.perf_counter() - started) * 1000),
            error_type=type(exc).__name__,
            error_message=sanitize_message(str(exc)),
        )
        raise
    else:
        _log_db_event(
            logging.INFO,
            DB_BOOTSTRAP_COMPLETED,
            "Database bootstrap completed",
            db_engine=_db_engine_name(DATABASE_URL),
            duration_ms=int((time.perf_counter() - started) * 1000),
        )


async def _inspect_existing_schema() -> dict[str, set[str]]:
    try:
        async with engine.connect() as conn:
            def inspect_db(sync_conn):
                from sqlalchemy import inspect
                inspector = inspect(sync_conn)
                return {
                    table_name: {
                        column["name"]
                        for column in inspector.get_columns(table_name)
                    }
                    for table_name in inspector.get_table_names()
                    if table_name != "alembic_version"
                }
            return await conn.run_sync(inspect_db)
    except Exception as e:
        _log_db_event(
            logging.WARNING,
            DB_INIT_FAILED,
            "Database initialization table inspection failed",
            db_engine=_db_engine_name(DATABASE_URL),
            error_type=type(e).__name__,
            error_message=sanitize_message(str(e)),
        )
        raise


def _validate_current_schema(schema: dict[str, set[str]]) -> None:
    expected_schema = {
        table.name: {column.name for column in table.columns}
        for table in Base.metadata.sorted_tables
    }
    actual_tables = set(schema)
    expected_tables = set(expected_schema)
    missing_tables = sorted(expected_tables - actual_tables)
    unexpected_tables = sorted(actual_tables - expected_tables)
    column_mismatches = {
        table_name: {
            "missing": sorted(expected_schema[table_name] - schema[table_name]),
            "unexpected": sorted(schema[table_name] - expected_schema[table_name]),
        }
        for table_name in sorted(expected_tables & actual_tables)
        if schema[table_name] != expected_schema[table_name]
    }
    if missing_tables or unexpected_tables or column_mismatches:
        _log_db_event(
            logging.ERROR,
            DB_INIT_FAILED,
            "Database initialization rejected a non-current schema",
            db_engine=_db_engine_name(DATABASE_URL),
            table_count=len(schema),
            missing_tables=missing_tables,
            unexpected_tables=unexpected_tables,
            column_mismatch_tables=sorted(column_mismatches),
            error_type="SchemaMismatchError",
        )
        raise ValueError(
            "CRITICAL DATABASE ERROR: The configured database does not match the current clean schema. "
            f"Missing tables: {missing_tables}; unexpected tables: {unexpected_tables}; "
            f"column mismatch tables: {sorted(column_mismatches)}. "
            "Configure an empty database and restart the application. Existing data is not migrated or repaired."
        )


async def init_db() -> None:
    """Bootstrap an empty database or validate an existing current schema."""
    started = time.perf_counter()
    _log_db_event(
        logging.INFO,
        DB_INIT_STARTED,
        "Database initialization started",
        db_engine=_db_engine_name(DATABASE_URL),
    )
    schema = await _inspect_existing_schema()
    if not schema:
        await bootstrap_db()
    else:
        _validate_current_schema(schema)

    _log_db_event(
        logging.INFO,
        DB_INIT_COMPLETED,
        "Database initialization completed",
        db_engine=_db_engine_name(DATABASE_URL),
        table_count=len(schema),
        duration_ms=int((time.perf_counter() - started) * 1000),
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
