import pytest
from fastapi.testclient import TestClient
from backend.main import app
from fastapi import HTTPException
from backend.api.dependencies.ownership import require_owned_project

@pytest.fixture(autouse=True)
def bypass_auth():
    from unittest.mock import MagicMock
    mock_project = MagicMock()
    mock_project.id = 123
    mock_project.public_id = "123"
    app.dependency_overrides[require_owned_project] = lambda: mock_project
    yield
    app.dependency_overrides.pop(require_owned_project, None)

# Test 1: Real CRUD route throwing unhandled Exception (via mock get_actors)
def test_real_route_exception_returns_clean_500(monkeypatch):
    from backend.api.routes.actor_routes import actor_service
    
    # Mock get_actors to raise an exception containing sensitive database URL
    async def mock_get_actors(*args, **kwargs):
        raise ValueError("database connection failure to postgresql://admin:db-secret@localhost/private api_key=plain-secret")
        
    monkeypatch.setattr(actor_service, "get_actors", mock_get_actors)
    
    client = TestClient(app, raise_server_exceptions=False)
    
    # Call list actors route
    response = client.get("/api/projects/123/actors")
    
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

# Test 2: Route throwing HTTPException status >= 500
def test_http_exception_500_returns_clean_500(monkeypatch):
    from backend.api.routes.actor_routes import actor_service
    
    # Mock get_actors to raise HTTPException(500)
    async def mock_get_actors(*args, **kwargs):
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve postgresql://admin:db-secret@localhost/private api_key=plain-secret"
        )
        
    monkeypatch.setattr(actor_service, "get_actors", mock_get_actors)
    
    client = TestClient(app, raise_server_exceptions=False)
    
    response = client.get("/api/projects/123/actors")
    assert response.status_code == 500
    res_json = response.json()
    assert res_json["detail"] == "Internal Server Error"
    assert "request_id" in res_json
    assert res_json["message"] == "An unhandled exception occurred in the backend."
    
    body_str = response.text
    assert "postgresql://" not in body_str
    assert "db-secret" not in body_str
    assert "plain-secret" not in body_str

# Test 3: Route throwing HTTPException status < 500 (e.g. 400, 401, 404) preserves detail and headers
def test_http_exception_4xx_preserves_detail_and_headers(monkeypatch):
    from backend.api.routes.actor_routes import actor_service
    
    # Test 400 with a dictionary detail
    async def mock_get_actors_400(*args, **kwargs):
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_failed", "fields": ["name"]},
            headers={"X-Custom-Header": "custom-value"}
        )
        
    monkeypatch.setattr(actor_service, "get_actors", mock_get_actors_400)
    
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/projects/123/actors")
    assert response.status_code == 400
    res_json = response.json()
    assert res_json["detail"] == {"error": "validation_failed", "fields": ["name"]}
    assert response.headers["X-Custom-Header"] == "custom-value"
