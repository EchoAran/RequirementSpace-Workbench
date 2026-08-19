import pytest
import logging
from fastapi.testclient import TestClient
from backend.main import app
from fastapi import HTTPException
from backend.api.dependencies.ownership import require_owned_project


def _events(caplog, event):
    return [record for record in caplog.records if getattr(record, "event", None) == event]

@pytest.fixture(autouse=True)
def bypass_auth(monkeypatch):
    from unittest.mock import MagicMock
    from backend.api.dependencies.project_access import require_project_member
    from backend.api.dependencies.auth import get_current_user
    mock_project = MagicMock()
    mock_project.id = 123
    mock_project.public_id = "123"
    mock_user = MagicMock()
    mock_user.id = 1
    app.dependency_overrides[require_owned_project] = lambda: mock_project
    app.dependency_overrides[require_project_member] = lambda: mock_project
    # 阶段 2 起 actor 路由直接依赖 get_current_user；未认证请求会被 401 拦截。
    app.dependency_overrides[get_current_user] = lambda: mock_user
    # 阶段 2 起路由会在 handler 内解析分支上下文；测试 DB 未必有 requirement_branches 表，
    # 因此跳过真实分支解析（本测试只关注异常清洗）。
    from backend.api.modules.requirements_core.actor import routes as actor_routes
    monkeypatch.setattr(
        actor_routes,
        "resolve_branch_context",
        lambda db, project_id, branch_ref=None, user_id=None: (
            None,
            None,
            {"can_write": True, "can_delete": False, "can_rename": False, "is_protected": False},
        ),
    )
    yield
    app.dependency_overrides.pop(require_owned_project, None)
    app.dependency_overrides.pop(require_project_member, None)
    app.dependency_overrides.pop(get_current_user, None)

# Test 1: Real CRUD route throwing unhandled Exception (via mock get_actors)
def test_real_route_exception_returns_clean_500(monkeypatch, caplog):
    monkeypatch.setenv("LOG_ENABLED", "true")
    monkeypatch.setenv("LOG_ENABLED_CATEGORIES", "request")
    from backend.api.modules.requirements_core.actor.routes import actor_service
    
    # Mock get_actors to raise an exception containing sensitive database URL
    async def mock_get_actors(*args, **kwargs):
        raise ValueError("database connection failure to postgresql://admin:db-secret@localhost/private api_key=plain-secret")
        
    monkeypatch.setattr(actor_service, "list_actors", mock_get_actors)
    
    client = TestClient(app, raise_server_exceptions=False)
    
    # Call list actors route
    with caplog.at_level(logging.INFO):
        response = client.get(
            "/api/projects/123/actors",
            headers={"X-Request-ID": "req-global-exception"},
        )
    
    # Assert 500 code and clean public structure
    assert response.status_code == 500
    res_json = response.json()
    assert res_json["detail"] == "Internal Server Error"
    assert "request_id" in res_json
    assert res_json["message"] == "An unhandled exception occurred in the backend."
    
    # Ensure no credentials leak in body
    body_str = response.text
    assert "postgresql://" not in body_str
    assert "db-secret" not in body_str
    assert "plain-secret" not in body_str
    assert "ValueError" not in body_str

    caught = _events(caplog, "http_exception_caught")
    assert caught
    fields = caught[-1].log_fields
    assert fields["request_id"] == res_json["request_id"] == "req-global-exception"
    assert fields["status_code"] == 500
    assert fields["error_type"] == "HTTPException"
    assert "db-secret" not in str(fields)
    assert "plain-secret" not in str(fields)

# Test 2: Route throwing HTTPException status >= 500
def test_http_exception_500_returns_clean_500(monkeypatch, caplog):
    monkeypatch.setenv("LOG_ENABLED", "true")
    monkeypatch.setenv("LOG_ENABLED_CATEGORIES", "request")
    from backend.api.modules.requirements_core.actor.routes import actor_service
    
    # Mock get_actors to raise HTTPException(500)
    async def mock_get_actors(*args, **kwargs):
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve postgresql://admin:db-secret@localhost/private api_key=plain-secret"
        )
        
    monkeypatch.setattr(actor_service, "list_actors", mock_get_actors)
    
    client = TestClient(app, raise_server_exceptions=False)
    
    with caplog.at_level(logging.INFO):
        response = client.get(
            "/api/projects/123/actors",
            headers={"X-Request-ID": "req-http-exception"},
        )
    assert response.status_code == 500
    res_json = response.json()
    assert res_json["detail"] == "Internal Server Error"
    assert "request_id" in res_json
    assert res_json["message"] == "An unhandled exception occurred in the backend."
    
    body_str = response.text
    assert "postgresql://" not in body_str
    assert "db-secret" not in body_str
    assert "plain-secret" not in body_str

    caught = _events(caplog, "http_exception_caught")
    assert caught
    fields = caught[-1].log_fields
    assert fields["request_id"] == res_json["request_id"] == "req-http-exception"
    assert fields["status_code"] == 500
    assert "db-secret" not in str(fields)
    assert "plain-secret" not in str(fields)

# Test 3: Route throwing HTTPException status < 500 (e.g. 400, 401, 404) preserves detail and headers
def test_http_exception_4xx_preserves_detail_and_headers(monkeypatch):
    from backend.api.modules.requirements_core.actor.routes import actor_service
    
    # Test 400 with a dictionary detail
    async def mock_get_actors_400(*args, **kwargs):
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_failed", "fields": ["name"]},
            headers={"X-Custom-Header": "custom-value"}
        )
        
    monkeypatch.setattr(actor_service, "list_actors", mock_get_actors_400)
    
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/projects/123/actors")
    assert response.status_code == 400
    res_json = response.json()
    assert res_json["detail"] == {"error": "validation_failed", "fields": ["name"]}
    assert response.headers["X-Custom-Header"] == "custom-value"
