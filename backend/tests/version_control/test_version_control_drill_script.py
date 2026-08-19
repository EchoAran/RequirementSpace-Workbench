"""
Version Control Migration Drill Script Tests (Phase 7).

验证 scripts/version_control_migration_drill.py 的 URL 脱敏：
报告不得泄露完整数据库 URL 或密码，只输出 db_type/host/database。
"""
import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "version_control_migration_drill.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("vc_migration_drill", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def drill_mod():
    return _load_module()


def test_masked_db_info_redacts_credentials(drill_mod):
    """脱敏结果不含密码或完整 URL。"""
    url = "postgresql://user:secret-pass@db.internal:5432/requirements"
    info = drill_mod._masked_db_info(url)
    assert info["db_type"] == "postgresql"
    assert info["host"] == "db.internal"
    assert info["port"] == 5432
    assert info["database"] == "requirements"
    serialized = str(info)
    assert "secret-pass" not in serialized
    assert "user:" not in serialized


def test_masked_db_info_sqlite(drill_mod):
    """SQLite 文件 URL 脱敏后保留路径库名，不含协议完整串。"""
    info = drill_mod._masked_db_info("sqlite:////tmp/drill.db")
    assert info["db_type"] == "sqlite"
    assert info["database"] == "/tmp/drill.db"


def test_masked_db_info_unparsable_falls_back_to_scheme(drill_mod):
    """对无法识别认证部分的 URL，脱敏结果不包含密码片段或完整 URL。"""
    info = drill_mod._masked_db_info("postgres://user:secret-pass@db.internal/requirements")
    serialized = str(info)
    assert "secret-pass" not in serialized
    assert "user:" not in serialized
    assert "db.internal" not in serialized or info["host"] == "db.internal"
    # 报告字段只包含 db_type/host/port/database，无完整 URL 字段。
    assert set(info.keys()) == {"db_type", "host", "port", "database"}
