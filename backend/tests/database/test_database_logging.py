import logging
import pytest

from backend.database import database


def _events(caplog, event):
    return [record for record in caplog.records if getattr(record, "event", None) == event]


class _FailingBeginContext:
    async def __aenter__(self):
        raise RuntimeError("bootstrap failed password=secret")

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FailingBootstrapEngine:
    def begin(self):
        return _FailingBeginContext()


def test_database_url_sanitizer_masks_postgresql_password():
    assert (
        database.sanitize_database_url("postgresql://user:secret@localhost:5432/requirement_space")
        == "postgresql://user:****@localhost:5432/requirement_space"
    )


def test_sync_migration_url_converts_async_drivers_without_credentials_leak():
    assert (
        database._sync_migration_url("sqlite+aiosqlite:///./requirement_space.db")
        == "sqlite:///./requirement_space.db"
    )
    assert (
        database._sync_migration_url("postgresql+asyncpg://user:secret@host/db")
        == "postgresql://user:secret@host/db"
    )


@pytest.mark.asyncio
async def test_bootstrap_db_logs_failed_event_when_engine_begin_fails(monkeypatch, caplog):
    monkeypatch.setenv("LOG_ENABLED", "true")
    monkeypatch.setenv("LOG_ENABLED_CATEGORIES", "db")
    monkeypatch.setattr(database, "engine", _FailingBootstrapEngine())

    with caplog.at_level(logging.INFO):
        with pytest.raises(RuntimeError):
            await database.bootstrap_db()

    events = [getattr(record, "event", None) for record in caplog.records]
    assert events == ["db_bootstrap_started", "db_bootstrap_failed"]
    failed = _events(caplog, "db_bootstrap_failed")
    assert len(failed) == 1
    fields = failed[0].log_fields
    assert fields["db_engine"] == database._db_engine_name(database.DATABASE_URL)
    assert fields["error_type"] == "RuntimeError"
    assert "duration_ms" in fields
    rendered = "\n".join(record.getMessage() + str(getattr(record, "log_fields", "")) for record in caplog.records)
    assert "password=secret" not in rendered
    assert "password=********" in rendered
