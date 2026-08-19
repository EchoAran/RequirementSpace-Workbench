#!/usr/bin/env python3
"""
Version Control Migration Drill (Phase 7).

在给定数据库 URL（SQLite 或 PostgreSQL）上演练版本控制的 alembic 迁移与基线回填，
输出结构化报告，供运维在上线前后对**一次性/隔离数据库**执行。

用法：
    python scripts/version_control_migration_drill.py            # 读 DATABASE_URL
    python scripts/version_control_migration_drill.py --url sqlite:///drill.db
    python scripts/version_control_migration_drill.py --url <postgres-url> --downgrade-rev 57a2677fc6b9

流程：upgrade head（计时）→ 采集行数 → 再次 upgrade（幂等）→ 可选 downgrade + re-upgrade
→ 输出 JSON 报告（各步时长、各表回填行数、幂等标志、往返标志）。

危险提示：本脚本会直接修改目标数据库（创建表、写入基线数据），
只允许对一次性/隔离的测试库执行，绝不可指向生产库。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

REPO_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = REPO_ROOT / "alembic.ini"

MIGRATION_TABLES = (
    "actors",
    "features",
    "feature_relations",
    "feature_scopes",
    "scenarios",
    "scenario_acceptance_criteria",
    "business_objects",
    "business_object_attributes",
    "flows",
    "flow_steps",
    "choice_groups",
    "choices",
)


def _sync_url(url: str) -> str:
    """把 async URL 归一化为同步驱动 URL（与 alembic/env.py 一致）。"""
    return (
        url.strip("'\" ")
        .replace("sqlite+aiosqlite://", "sqlite://")
        .replace("postgresql+asyncpg://", "postgresql://")
        .replace("postgres://", "postgresql://")
    )


def _masked_db_info(url: str) -> dict:
    """从数据库 URL 提取脱敏的 db_type / host / database，绝不包含密码或完整 URL。

    用于运维留档报告，避免把 PostgreSQL 用户名密码带进终端日志、CI Artifact 或工单。
    """
    try:
        from sqlalchemy.engine.url import make_url
        parsed = make_url(_sync_url(url))
        return {
            "db_type": parsed.drivername,
            "host": parsed.host or "",
            "port": parsed.port or "",
            "database": parsed.database or "",
        }
    except Exception:
        # 无法解析的 URL 只保留协议前缀，避免意外泄露任何片段。
        scheme = (url or "").split("://", 1)[0]
        return {"db_type": scheme or "unknown", "host": "", "port": "", "database": ""}


def _run_alembic(cmd: str, rev: str) -> float:
    """运行 alembic 命令并返回耗时（毫秒）；重定向 stdout 避免迁移 print 污染报告。"""
    from alembic import command
    from alembic.config import Config
    from contextlib import redirect_stdout
    import io

    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", _sync_url(os.environ["DRILL_URL"]))
    started = time.perf_counter()
    with redirect_stdout(io.StringIO()):
        if cmd == "upgrade":
            command.upgrade(cfg, rev)
        elif cmd == "downgrade":
            command.downgrade(cfg, rev)
    return int((time.perf_counter() - started) * 1000)


def _collect_counts(engine) -> dict:
    """采集关键表行数作为回填/幂等校验依据。"""
    insp = inspect(engine)
    counts: dict = {}
    for table in ("requirement_branches", "requirement_commits", *MIGRATION_TABLES):
        if insp.has_table(table):
            with engine.connect() as conn:
                counts[table] = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Version control migration drill")
    parser.add_argument("--url", help="database URL (default: DATABASE_URL env)")
    parser.add_argument(
        "--downgrade-rev",
        default="57a2677fc6b9",
        help="downgrade revision for roundtrip (default: pre-version-control rev)",
    )
    args = parser.parse_args()

    url = args.url or os.getenv("DATABASE_URL")
    if not url:
        print(json.dumps({"status": "error", "message": "no DATABASE_URL or --url provided"}))
        sys.exit(2)
    os.environ["DRILL_URL"] = url

    report: dict = {"status": "ok", "db_info": _masked_db_info(url), "steps": {}}

    # 1. upgrade head + 采集行数
    report["steps"]["upgrade_duration_ms"] = _run_alembic("upgrade", "head")
    engine = create_engine(_sync_url(url))
    report["counts_after_upgrade"] = _collect_counts(engine)
    engine.dispose()

    # 2. 再次 upgrade（幂等校验：行数不变）
    report["steps"]["upgrade_again_duration_ms"] = _run_alembic("upgrade", "head")
    engine = create_engine(_sync_url(url))
    counts_again = _collect_counts(engine)
    engine.dispose()
    report["idempotent"] = counts_again == report["counts_after_upgrade"]

    # 3. 可选 downgrade + re-upgrade 往返
    if args.downgrade_rev:
        report["steps"]["downgrade_duration_ms"] = _run_alembic("downgrade", args.downgrade_rev)
        report["steps"]["reupgrade_duration_ms"] = _run_alembic("upgrade", "head")
        engine = create_engine(_sync_url(url))
        report["counts_after_roundtrip"] = _collect_counts(engine)
        report["roundtrip"] = report["counts_after_roundtrip"] == report["counts_after_upgrade"]
        engine.dispose()
    else:
        report["roundtrip"] = None

    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["idempotent"] or (report["roundtrip"] is False):
        sys.exit(1)


if __name__ == "__main__":
    main()
