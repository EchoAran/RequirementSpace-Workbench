import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.database import database as database_module


class _ConnectionContext:
    def __init__(self, tables, project_columns):
        self._result = (tables, project_columns)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def run_sync(self, callback):
        return self._result


class _Engine:
    def __init__(self, tables, project_columns=()):
        self._tables = tables
        self._project_columns = project_columns

    def connect(self):
        return _ConnectionContext(self._tables, self._project_columns)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tables", "columns", "expected_error", "bootstraps", "upgrades"),
    [
        ([], [], None, 1, 0),
        (
            ["projects", "users"],
            ["name"],
            "missing the 'public_id' column",
            0,
            0,
        ),
        (
            ["projects"],
            ["public_id"],
            "'users' table is missing",
            0,
            0,
        ),
        (["projects", "users"], ["public_id"], None, 0, 1),
    ],
)
async def test_init_db_preserves_schema_decisions(
    monkeypatch,
    tables,
    columns,
    expected_error,
    bootstraps,
    upgrades,
):
    bootstrap = AsyncMock()
    upgrade = MagicMock()
    to_thread = AsyncMock(side_effect=lambda function: function())
    monkeypatch.setattr(database_module, "engine", _Engine(tables, columns))
    monkeypatch.setattr(database_module, "bootstrap_db", bootstrap)
    monkeypatch.setattr(database_module, "run_upgrade", upgrade)
    monkeypatch.setattr(asyncio, "to_thread", to_thread)

    if expected_error:
        with pytest.raises(ValueError, match=expected_error):
            await database_module.init_db()
    else:
        await database_module.init_db()

    assert bootstrap.await_count == bootstraps
    assert upgrade.call_count == upgrades


def test_run_upgrade_preserves_database_url_normalization(monkeypatch):
    fake_engine = SimpleNamespace(dispose=MagicMock())
    fake_inspector = SimpleNamespace(
        get_table_names=MagicMock(return_value=["users", "projects"])
    )
    upgrade = MagicMock()
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://user:secret@db-pooler.example/app"
        "?sslmode=require&channel_binding=require",
    )

    import alembic.command
    import sqlalchemy

    monkeypatch.setattr(sqlalchemy, "create_engine", MagicMock(return_value=fake_engine))
    monkeypatch.setattr(sqlalchemy, "inspect", MagicMock(return_value=fake_inspector))
    monkeypatch.setattr(alembic.command, "upgrade", upgrade)

    database_module.run_upgrade()

    config = upgrade.call_args.args[0]
    assert config.get_main_option("sqlalchemy.url") == (
        "postgresql://user:secret@db.example/app"
    )
    assert upgrade.call_args.args[1] == "head"
    fake_engine.dispose.assert_called_once_with()
