import logging

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.main import app


def _events(caplog, event):
    return [record for record in caplog.records if getattr(record, "event", None) == event]


@pytest.fixture(autouse=True)
def enable_request_logging(monkeypatch):
    monkeypatch.setenv("LOG_ENABLED", "true")
    monkeypatch.setenv("LOG_ENABLED_CATEGORIES", "request")


def _ensure_test_routes():
    if getattr(app.state, "phase3_request_logging_routes", False):
        return

    @app.get("/api/test-request-logging/{item_id}")
    async def test_request_logging_route(item_id: int):
        return {"item_id": item_id}

    @app.get("/api/test-request-logging-http-500")
    async def test_request_logging_http_500():
        raise HTTPException(status_code=500, detail="server failed api_key=plain-secret")

    @app.get("/api/test-request-logging-unhandled")
    async def test_request_logging_unhandled():
        raise ValueError("unhandled postgresql://admin:db-secret@localhost/private api_key=plain-secret")

    app.state.phase3_request_logging_routes = True


def test_request_logging_reuses_header_and_uses_route_template(caplog):
    _ensure_test_routes()
    client = TestClient(app, raise_server_exceptions=False)

    with caplog.at_level(logging.INFO):
        response = client.get(
            "/api/test-request-logging/42?secret=query-value",
            headers={"X-Request-ID": "req-from-client"},
        )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-from-client"
    completed = _events(caplog, "http_request_completed")
    assert completed
    event = completed[-1]
    fields = event.log_fields
    assert fields["request_id"] == "req-from-client"
    assert fields["method"] == "GET"
    assert fields["path"] == "/api/test-request-logging/{item_id}"
    assert fields["status_code"] == 200
    assert "duration_ms" in fields
    assert "query-value" not in str(fields)


def test_request_logging_generates_request_id_when_missing(caplog):
    _ensure_test_routes()
    client = TestClient(app, raise_server_exceptions=False)

    with caplog.at_level(logging.INFO):
        response = client.get("/api/test-request-logging/7")

    assert response.status_code == 200
    request_id = response.headers["X-Request-ID"]
    assert request_id
    completed = _events(caplog, "http_request_completed")
    assert completed[-1].log_fields["request_id"] == request_id


def test_http_exception_500_logs_same_request_id_and_sanitized_detail(caplog):
    _ensure_test_routes()
    client = TestClient(app, raise_server_exceptions=False)

    with caplog.at_level(logging.INFO):
        response = client.get(
            "/api/test-request-logging-http-500",
            headers={"X-Request-ID": "req-http-500"},
        )

    assert response.status_code == 500
    assert response.json()["request_id"] == "req-http-500"
    assert response.headers["X-Request-ID"] == "req-http-500"
    caught = _events(caplog, "http_exception_caught")
    assert caught
    fields = caught[-1].log_fields
    assert fields["request_id"] == "req-http-500"
    assert fields["status_code"] == 500
    assert "plain-secret" not in str(fields)


def test_unhandled_exception_logs_same_request_id_and_sanitized_traceback(caplog):
    _ensure_test_routes()
    client = TestClient(app, raise_server_exceptions=False)

    with caplog.at_level(logging.INFO):
        response = client.get(
            "/api/test-request-logging-unhandled",
            headers={"X-Request-ID": "req-unhandled"},
        )

    assert response.status_code == 500
    assert response.json()["request_id"] == "req-unhandled"
    assert response.headers["X-Request-ID"] == "req-unhandled"
    caught = _events(caplog, "global_exception_caught")
    assert caught
    fields = caught[-1].log_fields
    assert fields["request_id"] == "req-unhandled"
    assert fields["status_code"] == 500
    assert fields["error_type"] == "ValueError"
    assert "db-secret" not in str(fields)
    assert "plain-secret" not in str(fields)
