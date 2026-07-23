import os
import pytest
import sqlite3
from sqlalchemy import text, inspect
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from alembic.config import Config
from alembic import command

from backend.database.model import Base

@pytest.mark.asyncio
async def test_locale_migration_flow(tmp_path):
    db_file = tmp_path / "test_migration_flow.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    sync_url = f"sqlite:///{db_file}"

    # 1. Initialize Alembic config pointing to this temp DB
    # We must use sync connection for Alembic's default run_migrations
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", sync_url)

    # 2. Manually construct database schema at revision 8d2f4c9a1b7e
    # This bypasses a pre-existing bug in the legacy migration chain (which fails at 2a3d8257d849)
    def bootstrap_8d2f4c9a1b7e_schema(conn):
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute("""
            CREATE TABLE users (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, 
                email VARCHAR(255) NOT NULL UNIQUE, 
                password_hash VARCHAR(255) NOT NULL, 
                role VARCHAR(50) NOT NULL, 
                is_active BOOLEAN NOT NULL, 
                created_at DATETIME NOT NULL, 
                updated_at DATETIME NOT NULL
            )
        """)
        
        # Create projects table
        cursor.execute("""
            CREATE TABLE projects (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, 
                public_id VARCHAR(36) NOT NULL UNIQUE, 
                owner_user_id INTEGER NOT NULL, 
                name VARCHAR(255) NOT NULL, 
                description TEXT NOT NULL, 
                user_requirements TEXT NOT NULL, 
                kano_status VARCHAR(50) NOT NULL, 
                unlocked_stages VARCHAR(255) NOT NULL, 
                created_at DATETIME NOT NULL, 
                updated_at DATETIME NOT NULL,
                FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)
        
        # Create alembic_version table
        cursor.execute("""
            CREATE TABLE alembic_version (
                version_num VARCHAR(32) NOT NULL PRIMARY KEY
            )
        """)
        
        # Stamp the database at 8d2f4c9a1b7e
        cursor.execute("INSERT INTO alembic_version (version_num) VALUES ('8d2f4c9a1b7e')")
        
        # Insert initial test data
        cursor.execute(
            "INSERT INTO users (id, email, password_hash, role, is_active, created_at, updated_at) "
            "VALUES (101, 'old_user@example.com', 'pwd_hash', 'user', 1, '2026-07-13 00:00:00', '2026-07-13 00:00:00')"
        )
        cursor.execute(
            "INSERT INTO projects (id, public_id, owner_user_id, name, description, user_requirements, kano_status, unlocked_stages, created_at, updated_at) "
            "VALUES (201, 'proj_123', 101, 'Old Project', 'Desc', '', 'missing', '', '2026-07-13 00:00:00', '2026-07-13 00:00:00')"
        )
        
        conn.commit()

    conn = sqlite3.connect(db_file)
    bootstrap_8d2f4c9a1b7e_schema(conn)
    
    # Verify that columns do NOT exist initially
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(users)")
    cols = [c[1] for c in cursor.fetchall()]
    assert "preferred_locale" not in cols

    cursor.execute("PRAGMA table_info(projects)")
    cols = [c[1] for c in cursor.fetchall()]
    assert "content_locale" not in cols
    conn.close()

    # Temporarily remove DATABASE_URL to avoid overriding our custom setting in env.py
    old_db_url = os.environ.pop("DATABASE_URL", None)
    try:
        # 3. Upgrade to head (applies 57a2677fc6b9)
        def run_alembic_upgrade_to_head():
            command.upgrade(alembic_cfg, "head")

        await inspect_and_run_sync(run_alembic_upgrade_to_head)

        # 4. Verify columns exist and data has been backfilled
        def verify_post_upgrade_data(conn):
            cursor = conn.cursor()
            
            # Verify columns exist
            cursor.execute("PRAGMA table_info(users)")
            cols = [c[1] for c in cursor.fetchall()]
            assert "preferred_locale" in cols
            
            cursor.execute("PRAGMA table_info(projects)")
            cols = [c[1] for c in cursor.fetchall()]
            assert "content_locale" in cols

            # Verify old user is backfilled to 'zh-CN'
            cursor.execute("SELECT email, preferred_locale FROM users WHERE id=101")
            row = cursor.fetchone()
            assert row[0] == "old_user@example.com"
            assert row[1] == "zh-CN"

            # Verify old project content_locale is NULL
            cursor.execute("SELECT name, content_locale FROM projects WHERE id=201")
            row = cursor.fetchone()
            assert row[0] == "Old Project"
            assert row[1] is None

        conn = sqlite3.connect(db_file)
        verify_post_upgrade_data(conn)
        conn.close()

        # 5. Downgrade back to 8d2f4c9a1b7e
        def run_alembic_downgrade():
            command.downgrade(alembic_cfg, "8d2f4c9a1b7e")

        await inspect_and_run_sync(run_alembic_downgrade)

        # 6. Verify columns are removed but old data is fully preserved
        def verify_post_downgrade_data(conn):
            cursor = conn.cursor()
            
            # Verify columns are removed
            cursor.execute("PRAGMA table_info(users)")
            cols = [c[1] for c in cursor.fetchall()]
            assert "preferred_locale" not in cols
            
            cursor.execute("PRAGMA table_info(projects)")
            cols = [c[1] for c in cursor.fetchall()]
            assert "content_locale" not in cols

            # Verify old user data remains
            cursor.execute("SELECT email FROM users WHERE id=101")
            row = cursor.fetchone()
            assert row[0] == "old_user@example.com"

            # Verify old project data remains
            cursor.execute("SELECT name FROM projects WHERE id=201")
            row = cursor.fetchone()
            assert row[0] == "Old Project"

        conn = sqlite3.connect(db_file)
        verify_post_downgrade_data(conn)
        conn.close()
    finally:
        if old_db_url is not None:
            os.environ["DATABASE_URL"] = old_db_url


async def inspect_and_run_sync(sync_func):
    import asyncio
    # Run sync function in executor or loop
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, sync_func)


