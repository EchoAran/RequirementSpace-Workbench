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


import os
import urllib.parse

raw_db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./requirement_space.db").strip("'\" ")

if raw_db_url.startswith("postgresql://") or raw_db_url.startswith("postgres://"):
    # Translate scheme to postgresql+asyncpg
    scheme = "postgresql+asyncpg"
    rest = raw_db_url.split("://", 1)[1]
    # Use dummy scheme http to let urlparse extract netloc correctly
    parsed = urllib.parse.urlparse(f"http://{rest}")
    
    # Strip 'sslmode' as asyncpg does not support it and throws TypeError
    query_params = urllib.parse.parse_qs(parsed.query)
    query_params.pop("sslmode", None)
    new_query = urllib.parse.urlencode(query_params, doseq=True)
    
    DATABASE_URL = f"{scheme}://{parsed.netloc}{parsed.path}"
    if new_query:
        DATABASE_URL += f"?{new_query}"
        
    engine: AsyncEngine = create_async_engine(
        DATABASE_URL,
        echo=False,
        future=True,
        connect_args={"ssl": True, "timeout": 5}
    )
else:
    DATABASE_URL = raw_db_url
    engine: AsyncEngine = create_async_engine(
        DATABASE_URL,
        echo=False,
        future=True,
    )


@event.listens_for(Engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
    # Only run PRAGMAs on sqlite connections
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

    print(">>> [DATABASE UPGRADE] Starting run_upgrade()...", flush=True)
    base_dir = Path(__file__).resolve().parents[2]
    db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./requirement_space.db").strip("'\" ")
    
    # Obfuscate password in URL for safe logging
    safe_url = db_url
    if "@" in db_url:
        try:
            parts = db_url.split("@", 1)
            scheme_and_user = parts[0].split("://", 1)
            if ":" in scheme_and_user[1]:
                scheme_and_user[1] = scheme_and_user[1].split(":", 1)[0] + ":****"
            safe_url = f"{scheme_and_user[0]}://{scheme_and_user[1]}@{parts[1]}"
        except Exception:
            safe_url = "[Obfuscated URL due to parsing exception]"
    print(f">>> [DATABASE UPGRADE] Resolved DATABASE_URL: {safe_url}", flush=True)

    is_sqlite = "sqlite" in db_url
    db_path = None

    if is_sqlite:
        print(">>> [DATABASE UPGRADE] Database engine detected: SQLite", flush=True)
        if "sqlite+aiosqlite:///" in db_url:
            db_path_str = db_url.replace("sqlite+aiosqlite:///", "")
            if db_path_str.startswith("/") or ":" in db_path_str:
                db_path = Path(db_path_str)
            else:
                db_path = base_dir / db_path_str
        else:
            db_path = base_dir / "requirement_space.db"
    else:
        print(">>> [DATABASE UPGRADE] Database engine detected: PostgreSQL", flush=True)

    alembic_ini_path = base_dir / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("script_location", str(base_dir / "alembic"))
    
    # Convert async engine URL to sync engine URL for Alembic sync migrations
    if db_url.startswith("sqlite+aiosqlite://"):
        alembic_url = db_url.replace("sqlite+aiosqlite://", "sqlite://")
    elif db_url.startswith("postgresql+asyncpg://"):
        alembic_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    elif db_url.startswith("postgresql://"):
        alembic_url = db_url
    elif db_url.startswith("postgres://"):
        alembic_url = db_url.replace("postgres://", "postgresql://")
    else:
        alembic_url = db_url
        
    alembic_cfg.set_main_option("sqlalchemy.url", alembic_url)
    
    safe_alembic_url = alembic_url
    if "@" in alembic_url:
        try:
            parts = alembic_url.split("@", 1)
            scheme_and_user = parts[0].split("://", 1)
            if ":" in scheme_and_user[1]:
                scheme_and_user[1] = scheme_and_user[1].split(":", 1)[0] + ":****"
            safe_alembic_url = f"{scheme_and_user[0]}://{scheme_and_user[1]}@{parts[1]}"
        except Exception:
            safe_alembic_url = "[Obfuscated Alembic URL]"
    print(f">>> [DATABASE UPGRADE] Configured Alembic sync URL: {safe_alembic_url}", flush=True)

    print(">>> [DATABASE UPGRADE] Triggering command.upgrade(alembic_cfg, 'head')...", flush=True)
    try:
        command.upgrade(alembic_cfg, "head")
        print(">>> [DATABASE UPGRADE] command.upgrade(...) completed successfully!", flush=True)
    except Exception as e:
        print(f">>> [DATABASE UPGRADE] command.upgrade(...) FAILED: {str(e)}", flush=True)
        raise e

    # Only run SQLite-specific repairs if using SQLite
    if is_sqlite and db_path and db_path.exists():
        print(">>> [DATABASE UPGRADE] Running SQLite-specific repairs...", flush=True)
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
            print(">>> [DATABASE UPGRADE] SQLite table repair check completed.", flush=True)
        except Exception as ex:
            print(f">>> [DATABASE UPGRADE] SQLite table repair failed (non-fatal): {str(ex)}", flush=True)

        # Data migration: Convert legacy Chinese scope status to canonical English keys
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("UPDATE feature_scopes SET status = 'current' WHERE status = '本期';")
            cursor.execute("UPDATE feature_scopes SET status = 'postponed' WHERE status = '暂缓';")
            cursor.execute("UPDATE feature_scopes SET status = 'exclude' WHERE status = '排除';")
            conn.commit()
            cursor.close()
            conn.close()
            print(">>> [DATABASE UPGRADE] SQLite data migration completed.", flush=True)
        except Exception as ex:
            print(f">>> [DATABASE UPGRADE] SQLite data migration failed (non-fatal): {str(ex)}", flush=True)


async def init_db() -> None:
    import asyncio
    await asyncio.to_thread(run_upgrade)


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
