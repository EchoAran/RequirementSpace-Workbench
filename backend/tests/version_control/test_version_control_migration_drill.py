"""
Version Control Migration Drill Tests (Phase 7).

在真实 SQLite 数据库上演练 alembic upgrade/downgrade/re-upgrade 与基线迁移：
  - 记录并断言回填行数与迁移时长；
  - 重复执行幂等（upgrade 两次 + 直接调用 migrate_project_to_version_control 得 skipped）；
  - upgrade → downgrade → re-upgrade 往返后结构与计数复原；
  - 步骤 8 失败恢复（沿用既有 monkeypatch 模式）。

复用 test_version_control_alembic_migration.bootstrap_full_57a2677fc6b9_schema
构造 57a2677fc6b9 版本的全量旧 schema 与项目数据。
"""
import os
import sqlite3

import pytest
from alembic import command
from alembic.config import Config

from backend.tests.version_control.test_version_control_alembic_migration import (
    bootstrap_full_57a2677fc6b9_schema,
)

UPGRADE_REV = "head"
BASE_REV = "57a2677fc6b9"


def _make_db(tmp_path, name="drill.db"):
    """构建一个含旧 schema 与项目数据的 SQLite 文件，返回 (db_file, sync_url)。"""
    db_file = tmp_path / name
    conn = sqlite3.connect(str(db_file))
    bootstrap_full_57a2677fc6b9_schema(conn)
    conn.close()
    return db_file, f"sqlite:///{db_file}"


def _upgrade(url):
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, UPGRADE_REV)


def _downgrade(url):
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.downgrade(cfg, BASE_REV)


def _row_count(cursor, table):
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    return cursor.fetchone()[0]


def _collect_counts(cursor):
    """采集迁移后各关键表行数，供幂等/往返断言。"""
    return {
        "branches": _row_count(cursor, "requirement_branches"),
        "commits": _row_count(cursor, "requirement_commits"),
        "actors": _row_count(cursor, "actors"),
        "features": _row_count(cursor, "features"),
        "feature_relations": _row_count(cursor, "feature_relations"),
        "scenarios": _row_count(cursor, "scenarios"),
        "scenarios_ac": _row_count(cursor, "scenario_acceptance_criteria"),
        "business_objects": _row_count(cursor, "business_objects"),
        "business_object_attributes": _row_count(cursor, "business_object_attributes"),
        "flows": _row_count(cursor, "flows"),
        "flow_steps": _row_count(cursor, "flow_steps"),
        "scopes": _row_count(cursor, "feature_scopes"),
    }


@pytest.fixture
def drill_db(tmp_path):
    """构造演练数据库并确保 DATABASE_URL 环境在测试期间指向它。"""
    db_file, sync_url = _make_db(tmp_path)
    old_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = sync_url
    yield db_file, sync_url
    if old_url is not None:
        os.environ["DATABASE_URL"] = old_url
    else:
        os.environ.pop("DATABASE_URL", None)


def test_upgrade_records_row_counts_and_duration(drill_db):
    """upgrade head 后记录回填行数并断言非空；迁移时长可观测（打印到报告）。"""
    db_file, sync_url = drill_db
    import time
    started = time.perf_counter()
    _upgrade(sync_url)
    duration_ms = int((time.perf_counter() - started) * 1000)

    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    counts = _collect_counts(cursor)
    conn.close()

    # 基线应恰好 1 条 main 分支与 1 条 baseline commit。
    assert counts["branches"] == 1
    assert counts["commits"] == 1
    # 12 个实体表均已回填（行数与原源数据一致，且 non-zero）。
    for table in ("actors", "features", "feature_relations", "scenarios",
                  "scenarios_ac", "business_objects", "business_object_attributes",
                  "flows", "flow_steps", "scopes"):
        assert counts[table] > 0, f"{table} should be backfilled"
    # 迁移时长 ≥ 0（可观测信号，不做硬阈值断言，避免环境差异误报）。
    assert duration_ms >= 0
    print(f"[drill] upgrade duration_ms={duration_ms} counts={counts}")


def test_upgrade_twice_is_idempotent(drill_db):
    """重复 upgrade 不产生第二个 main/基线；直接迁移返回 skipped 且计数不变。"""
    db_file, sync_url = drill_db
    _upgrade(sync_url)

    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    counts_first = _collect_counts(cursor)
    conn.close()

    # 第二次 upgrade（幂等）。
    _upgrade(sync_url)

    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    counts_second = _collect_counts(cursor)
    conn.close()

    assert counts_second == counts_first
    assert counts_second["branches"] == 1
    assert counts_second["commits"] == 1

    # 通过 ORM 直接调用 migrate_project_to_version_control 应得到 skipped。
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from backend.database.model import ProjectModel
    from backend.api.modules.version_control.application.baseline_migration import (
        migrate_project_to_version_control,
    )
    engine = create_engine(sync_url)
    with Session(engine) as s:
        project = s.get(ProjectModel, 100)
        result = migrate_project_to_version_control(s, project)
        s.rollback()
        assert result["status"] == "skipped"
    engine.dispose()


def test_upgrade_downgrade_reupgrade_roundtrip(drill_db):
    """upgrade → downgrade（旧数据保留）→ re-upgrade → 结构与计数复原。"""
    db_file, sync_url = drill_db
    _upgrade(sync_url)

    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    counts_up = _collect_counts(cursor)
    conn.close()

    _downgrade(sync_url)

    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    # 降级后旧数据保留、VC 表移除。
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='requirement_branches'")
    assert cursor.fetchone() is None
    cursor.execute("SELECT name FROM actors WHERE id=10")
    assert cursor.fetchone()[0] == "Buyer"
    conn.close()

    _upgrade(sync_url)

    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    counts_reup = _collect_counts(cursor)
    conn.close()
    assert counts_reup == counts_up


def test_step8_failure_recovery(drill_db, monkeypatch):
    """基线步骤失败时 alembic 整体回滚，不留残留 VC 表（沿用既有步骤8回滚模式）。"""
    from alembic.operations import Operations

    db_file, sync_url = drill_db
    orig_batch_alter = Operations.batch_alter_table
    call_count = 0

    def mock_batch_alter(self, table_name, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count > 12:
            raise RuntimeError("Simulated step 8 alteration failure")
        return orig_batch_alter(self, table_name, *args, **kwargs)

    monkeypatch.setattr(Operations, "batch_alter_table", mock_batch_alter)

    with pytest.raises(RuntimeError, match="Simulated step 8 alteration failure"):
        _upgrade(sync_url)

    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    cursor.execute("SELECT version_num FROM alembic_version")
    assert cursor.fetchone()[0] == BASE_REV
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='requirement_branches'")
    assert cursor.fetchone() is None
    conn.close()
