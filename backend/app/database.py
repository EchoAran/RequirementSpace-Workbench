from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "backend" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_URL = f"sqlite:///{(DATA_DIR / 'requirement_space.db').as_posix()}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class Base(DeclarativeBase):
    pass


def _table_exists(conn, table_name: str) -> bool:
    return bool(
        conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name=:table_name"),
            {"table_name": table_name},
        ).scalar()
    )


def _get_columns(conn, table_name: str) -> list[str]:
    return [row[1] for row in conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()]


def initialize_database() -> None:
    # Import models so SQLAlchemy metadata includes the latest table definitions.
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def inspect_schema_drift() -> dict[str, dict[str, list[str]]]:
    # Ensure SQLAlchemy metadata is populated before comparing with SQLite schema.
    from . import models  # noqa: F401

    drift: dict[str, dict[str, list[str]]] = {}
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not _table_exists(conn, table.name):
                continue
            model_columns = {column.name for column in table.columns}
            actual_columns = set(_get_columns(conn, table.name))
            missing = sorted(model_columns - actual_columns)
            extra = sorted(actual_columns - model_columns)
            if missing or extra:
                drift[table.name] = {"missing": missing, "extra": extra}
    return drift


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
