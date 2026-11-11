from unittest.mock import AsyncMock

import pytest

from backend.database import database as database_module


class _ConnectionContext:
    def __init__(self, schema):
        self._result = schema

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def run_sync(self, callback):
        return self._result


class _Engine:
    def __init__(self, schema):
        self._schema = schema

    def connect(self):
        return _ConnectionContext(self._schema)


@pytest.mark.asyncio
async def test_init_db_bootstraps_only_empty_database(monkeypatch):
    bootstrap = AsyncMock()
    monkeypatch.setattr(database_module, "engine", _Engine({}))
    monkeypatch.setattr(database_module, "bootstrap_db", bootstrap)

    await database_module.init_db()

    bootstrap.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_init_db_accepts_exact_current_schema(monkeypatch):
    schema = {
        table.name: {column.name for column in table.columns}
        for table in database_module.Base.metadata.sorted_tables
    }
    bootstrap = AsyncMock()
    monkeypatch.setattr(database_module, "engine", _Engine(schema))
    monkeypatch.setattr(database_module, "bootstrap_db", bootstrap)

    await database_module.init_db()

    bootstrap.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutate_schema, expected_message",
    [
        (lambda schema: schema.pop("flow_transitions"), "Missing tables: ['flow_transitions']"),
        (lambda schema: schema.update({"flow_step_next": {"source_id", "target_id"}}), "unexpected tables: ['flow_step_next']"),
        (lambda schema: schema["projects"].remove("public_id"), "column mismatch tables: ['projects']"),
    ],
)
async def test_init_db_rejects_non_current_schema(
    monkeypatch,
    mutate_schema,
    expected_message,
):
    schema = {
        table.name: {column.name for column in table.columns}
        for table in database_module.Base.metadata.sorted_tables
    }
    mutate_schema(schema)
    bootstrap = AsyncMock()
    monkeypatch.setattr(database_module, "engine", _Engine(schema))
    monkeypatch.setattr(database_module, "bootstrap_db", bootstrap)

    with pytest.raises(ValueError, match=expected_message.replace("[", r"\[").replace("]", r"\]")):
        await database_module.init_db()

    bootstrap.assert_not_awaited()
