"""
Version Control Migration Feature Flag Tests (Phase 7).
验证 VERSION_CONTROL_MIGRATION_ENABLED kill-switch：
  - 关闭时 _ensure_version_control_baselines 早退并记录 VC_BASELINE_AUTO_DISABLED；
  - 开启时（测试环境）走到 pytest 守卫早退，不触发迁移。
"""
import logging


def test_migration_disabled_skips_baselines(monkeypatch, caplog):
    """开关关闭时自动迁移早退，且记录 VC_BASELINE_AUTO_DISABLED 事件。"""
    import backend.core.config as config
    from backend.database.database import _ensure_version_control_baselines

    monkeypatch.setattr(config, "VERSION_CONTROL_MIGRATION_ENABLED", False)

    with caplog.at_level(logging.INFO, logger="backend"):
        _ensure_version_control_baselines()

    events = [r for r in caplog.records if getattr(r, "event", None) == "vc_baseline_auto_disabled"]
    assert events, "VC_BASELINE_AUTO_DISABLED should be logged when flag disabled"


def test_migration_enabled_reaches_pytest_guard(monkeypatch, caplog):
    """开关开启时（测试环境）走到 pytest 守卫早退，不触发迁移，也不记录 disabled 事件。"""
    import backend.core.config as config
    from backend.database.database import _ensure_version_control_baselines

    monkeypatch.setattr(config, "VERSION_CONTROL_MIGRATION_ENABLED", True)

    with caplog.at_level(logging.INFO, logger="backend"):
        _ensure_version_control_baselines()

    events = [r for r in caplog.records if getattr(r, "event", None) == "vc_baseline_auto_disabled"]
    assert not events, "No disabled event expected when flag enabled"
