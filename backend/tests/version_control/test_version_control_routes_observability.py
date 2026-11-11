"""
Version Control Route Observability Tests (Phase 7, DB-free).

验证提交/合并路由在异常路径调用 audit_vc_failure（失败审计），且不改变 HTTP 状态码/错误码。
采用 dependency_overrides 替换 get_session/get_current_user/require_project_member，
monkeypatch service 抛异常，断言审计函数被调用。
"""
from fastapi.testclient import TestClient

from backend.database.model import ProjectModel, UserModel
from backend.main import app


def _make_client(monkeypatch, captured, session_stub):
    """构造替换了认证/会话依赖的 TestClient。"""
    from backend.api.dependencies.auth import get_current_user
    from backend.api.dependencies.ownership import require_project_member
    from backend.database.database import get_session

    async def _fake_get_current_user():
        return UserModel(id=1, email="user@test.com", password_hash="h", role="admin")

    def _fake_require_project_member():
        return ProjectModel(id=1, owner_user_id=1, name="P", description="")

    def _fake_get_session():
        yield session_stub

    app.dependency_overrides[get_current_user] = _fake_get_current_user
    app.dependency_overrides[require_project_member] = _fake_require_project_member
    app.dependency_overrides[get_session] = _fake_get_session

    # 捕获 audit_vc_failure 调用：路由模块以 from-import 绑定局部名，须逐个 monkeypatch。
    import backend.api.modules.version_control.commit_routes as commit_routes_mod
    import backend.api.modules.version_control.merge_routes as merge_routes_mod

    async def _fake_audit_failure(**kwargs):
        captured["audit"] = kwargs

    monkeypatch.setattr(commit_routes_mod, "audit_vc_failure", _fake_audit_failure)
    monkeypatch.setattr(merge_routes_mod, "audit_vc_failure", _fake_audit_failure)
    return TestClient(app)


def _session_stub(result_or_exc, is_exc=False):
    """构造一个仅实现 run_sync 的桩 Session。"""
    class _Stub:
        def run_sync(self, fn, **kw):
            if is_exc:
                raise result_or_exc
            return result_or_exc
    return _Stub()


def test_commit_head_changed_records_failure_audit(monkeypatch):
    """提交冲突（HeadChangedError）→ 409 + audit_vc_failure(action_type=commit_head_changed)。"""
    from backend.api.modules.version_control.application.errors import HeadChangedError

    captured = {}
    err = HeadChangedError("head changed", current_head_commit_id=5, current_head_public_id="abc")
    client = _make_client(monkeypatch, captured, _session_stub(err, is_exc=True))

    resp = client.post(
        "/api/projects/p1/commits",
        json={"message": "m", "expected_head_commit_public_id": "abc"},
        params={"branch": "main"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "head_changed"
    assert captured["audit"]["action_type"] == "commit_head_changed"
    assert captured["audit"]["error_type"] == "HeadChangedError"

    app.dependency_overrides.clear()


def test_merge_conflict_records_failure_audit(monkeypatch):
    """合并冲突（MergeConflictError）→ 409 + audit_vc_failure(action_type=merge_conflict)。"""
    from backend.api.modules.version_control.application.errors import (
        MergeConflictError,
    )

    captured = {}
    err = MergeConflictError("conflict", conflict_ids=["c1"])
    client = _make_client(monkeypatch, captured, _session_stub(err, is_exc=True))

    resp = client.post(
        "/api/projects/p1/merge-requests/mr1/merge",
        json={
            "resolutions": [],
            "merge_base_public_id": "b",
            "source_head_public_id": "s",
            "target_head_public_id": "t",
        },
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "merge_conflict"
    assert captured["audit"]["action_type"] == "merge_conflict"
    assert captured["audit"]["conflict_ids"] == ["c1"]

    app.dependency_overrides.clear()


def test_merge_blocked_records_failure_audit(monkeypatch):
    """合并阻塞（MergeBlockedError）→ 400 + audit_vc_failure(action_type=merge_blocked)。"""
    from backend.api.modules.version_control.application.errors import MergeBlockedError

    captured = {}
    err = MergeBlockedError("blocked", reasons=["missing_approval"])
    client = _make_client(monkeypatch, captured, _session_stub(err, is_exc=True))

    resp = client.post(
        "/api/projects/p1/merge-requests/mr1/merge",
        json={
            "resolutions": [],
            "merge_base_public_id": "b",
            "source_head_public_id": "s",
            "target_head_public_id": "t",
        },
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "merge_blocked"
    assert captured["audit"]["action_type"] == "merge_blocked"
    assert captured["audit"]["reasons"] == ["missing_approval"]

    app.dependency_overrides.clear()
