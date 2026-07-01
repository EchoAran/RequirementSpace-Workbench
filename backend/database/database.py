from __future__ import annotations

from collections.abc import AsyncGenerator
import logging
import time

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
    DB_MIGRATION_COMPLETED,
    DB_MIGRATION_FAILED,
    DB_MIGRATION_STARTED,
    DB_SQLITE_REPAIR_COMPLETED,
    DB_SQLITE_REPAIR_FAILED,
    DB_SQLITE_REPAIR_STARTED,
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


def run_upgrade() -> None:
    import sqlite3
    from pathlib import Path
    from alembic.config import Config
    from alembic import command

    started = time.perf_counter()
    _log_db_event(
        logging.INFO,
        DB_MIGRATION_STARTED,
        "Database migration started",
        alembic_target="head",
    )
    base_dir = Path(__file__).resolve().parents[2]
    db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./requirement_space.db").strip("'\" ")
    if "-pooler" in db_url:
        db_url = db_url.replace("-pooler", "")

    # Strip 'sslmode' and 'channel_binding' query parameters as psycopg2 does not support them
    if "?" in db_url:
        import urllib.parse
        base_part, query_part = db_url.split("?", 1)
        params = urllib.parse.parse_qs(query_part)
        params.pop("sslmode", None)
        params.pop("channel_binding", None)
        new_query = urllib.parse.urlencode(params, doseq=True)
        db_url = f"{base_part}?{new_query}" if new_query else base_part

    table_count = None
    try:
        from sqlalchemy import create_engine, inspect
        sync_url = _sync_migration_url(db_url)
        temp_engine = create_engine(sync_url, connect_args={"connect_timeout": 5} if "sqlite" not in sync_url else {})
        inspector = inspect(temp_engine)
        tables = inspector.get_table_names()
        table_count = len(tables)
        _log_db_event(
            logging.INFO,
            DB_MIGRATION_STARTED,
            "Database migration table inspection completed",
            db_engine=_db_engine_name(db_url),
            table_count=table_count,
            required_table="users",
            required_table_exists="users" in tables,
        )
        temp_engine.dispose()
    except Exception as ex:
        _log_db_event(
            logging.WARNING,
            DB_MIGRATION_STARTED,
            "Database migration table inspection failed",
            db_engine=_db_engine_name(db_url),
            error_type=type(ex).__name__,
            error_message=sanitize_message(str(ex)),
        )

    is_sqlite = "sqlite" in db_url
    db_path = None

    if is_sqlite:
        if "sqlite+aiosqlite:///" in db_url:
            db_path_str = db_url.replace("sqlite+aiosqlite:///", "")
            if db_path_str.startswith("/") or ":" in db_path_str:
                db_path = Path(db_path_str)
            else:
                db_path = base_dir / db_path_str
        else:
            db_path = base_dir / "requirement_space.db"

    alembic_ini_path = base_dir / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("script_location", str(base_dir / "alembic"))

    alembic_url = _sync_migration_url(db_url)

    alembic_cfg.set_main_option("sqlalchemy.url", alembic_url)

    _log_db_event(
        logging.INFO,
        DB_MIGRATION_STARTED,
        "Database migration configured",
        db_engine=_db_engine_name(db_url),
        database_url=sanitize_database_url(db_url),
        alembic_target="head",
        table_count=table_count,
    )

    try:
        command.upgrade(alembic_cfg, "head")
    except Exception as e:
        _log_db_event(
            logging.ERROR,
            DB_MIGRATION_FAILED,
            "Database migration failed",
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
            DB_MIGRATION_COMPLETED,
            "Database migration completed",
            db_engine=_db_engine_name(db_url),
            alembic_target="head",
            duration_ms=int((time.perf_counter() - started) * 1000),
        )

    # Only run SQLite-specific repairs if using SQLite
    if is_sqlite and db_path and db_path.exists():
        _log_db_event(
            logging.INFO,
            DB_SQLITE_REPAIR_STARTED,
            "SQLite repair checks started",
            db_engine="sqlite",
            repair="issue_repair_drafts_table",
        )
        # Repair case: if a migration was previously "stamp"ed without running its
        # DDL (old behaviour), the alembic_version says "up to date" but the table
        # is missing.  Detect and fix.
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='issue_repair_drafts';"
            )
            if cursor.fetchone() is None:
                from backend.database.model import IssueRepairDraftModel
                from sqlalchemy import create_engine
                sync_engine = create_engine(f"sqlite:///{db_path}")
                IssueRepairDraftModel.__table__.create(sync_engine, checkfirst=True)
                sync_engine.dispose()
            cursor.close()
            conn.close()
            _log_db_event(
                logging.INFO,
                DB_SQLITE_REPAIR_COMPLETED,
                "SQLite table repair check completed",
                db_engine="sqlite",
                repair="issue_repair_drafts_table",
            )
        except Exception as ex:
            _log_db_event(
                logging.WARNING,
                DB_SQLITE_REPAIR_FAILED,
                "SQLite table repair failed",
                db_engine="sqlite",
                repair="issue_repair_drafts_table",
                error_type=type(ex).__name__,
                error_message=sanitize_message(str(ex)),
            )

        # Data migration: Convert legacy Chinese scope status to canonical English keys
        _log_db_event(
            logging.INFO,
            DB_SQLITE_REPAIR_STARTED,
            "SQLite data repair started",
            db_engine="sqlite",
            repair="legacy_scope_status_values",
        )
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("UPDATE feature_scopes SET status = 'current' WHERE status = '本期';")
            cursor.execute("UPDATE feature_scopes SET status = 'postponed' WHERE status = '暂缓';")
            cursor.execute("UPDATE feature_scopes SET status = 'exclude' WHERE status = '排除';")
            conn.commit()
            cursor.close()
            conn.close()
            _log_db_event(
                logging.INFO,
                DB_SQLITE_REPAIR_COMPLETED,
                "SQLite data repair completed",
                db_engine="sqlite",
                repair="legacy_scope_status_values",
            )
        except Exception as ex:
            _log_db_event(
                logging.WARNING,
                DB_SQLITE_REPAIR_FAILED,
                "SQLite data repair failed",
                db_engine="sqlite",
                repair="legacy_scope_status_values",
                error_type=type(ex).__name__,
                error_message=sanitize_message(str(ex)),
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


async def init_db() -> None:
    """Initialize database: bootstrap from metadata if database is completely empty.
    If database contains existing tables but lacks 'users', raise an error to prevent partial schema generation."""
    project_columns = []
    started = time.perf_counter()
    _log_db_event(
        logging.INFO,
        DB_INIT_STARTED,
        "Database initialization started",
        db_engine=_db_engine_name(DATABASE_URL),
    )
    try:
        async with engine.connect() as conn:
            def inspect_db(sync_conn):
                from sqlalchemy import inspect
                inspector = inspect(sync_conn)
                tables = inspector.get_table_names()
                columns = []
                if "projects" in tables:
                    columns = [c["name"] for c in inspector.get_columns("projects")]
                return tables, columns
            tables, project_columns = await conn.run_sync(inspect_db)
    except Exception as e:
        _log_db_event(
            logging.WARNING,
            DB_INIT_FAILED,
            "Database initialization table inspection failed",
            db_engine=_db_engine_name(DATABASE_URL),
            error_type=type(e).__name__,
            error_message=sanitize_message(str(e)),
        )
        tables = ["users"]  # Fallback to assume it's already initialized
        project_columns = ["public_id"]

    # Exclude alembic_version from checking if it exists
    non_alembic_tables = [t for t in tables if t != "alembic_version"]

    if not non_alembic_tables:
        await bootstrap_db()
        _log_db_event(
            logging.INFO,
            DB_INIT_COMPLETED,
            "Database initialization completed",
            db_engine=_db_engine_name(DATABASE_URL),
            table_count=len(non_alembic_tables),
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
    elif "projects" in non_alembic_tables and "public_id" not in project_columns:
        _log_db_event(
            logging.ERROR,
            DB_INIT_FAILED,
            "Database initialization failed due to legacy projects schema",
            db_engine=_db_engine_name(DATABASE_URL),
            required_table="projects",
            table_count=len(non_alembic_tables),
            error_type="LegacySchemaError",
        )
        raise ValueError(
            "CRITICAL DATABASE ERROR: The database 'projects' table is missing the 'public_id' column. "
            "To support project public identifier and URL improvement, you must reset the database.\n"
            "Please delete the database file ('requirement_space.db', 'requirement_space.db-wal', 'requirement_space.db-shm') "
            "or recreate your PostgreSQL schema, then restart the application."
        )
    elif "users" not in non_alembic_tables:
        # Database contains old tables, but users table is missing
        _log_db_event(
            logging.ERROR,
            DB_INIT_FAILED,
            "Database initialization failed due to missing users table",
            db_engine=_db_engine_name(DATABASE_URL),
            required_table="users",
            table_count=len(non_alembic_tables),
            error_type="LegacySchemaError",
        )
        raise ValueError(
            "CRITICAL DATABASE ERROR: The database contains existing tables from a legacy version, "
            "but the 'users' table is missing. Because P0 introduces non-nullable owner constraints, "
            "rebuilding the schema requires a fresh database.\n"
            "Please delete the database file ('requirement_space.db', 'requirement_space.db-wal', 'requirement_space.db-shm') "
            "or recreate your PostgreSQL schema, then restart the application."
        )
    else:
        import asyncio
        await asyncio.to_thread(run_upgrade)
        _log_db_event(
            logging.INFO,
            DB_INIT_COMPLETED,
            "Database initialization completed",
            db_engine=_db_engine_name(DATABASE_URL),
            table_count=len(non_alembic_tables),
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
