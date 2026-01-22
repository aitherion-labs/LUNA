from fastapi.testclient import TestClient

from main import app


def test_health_public_and_request_id_generated():
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"
    # Request-ID should be present in response headers
    assert "x-request-id" in r.headers
    assert r.headers["x-request-id"]


def test_request_id_propagation():
    client = TestClient(app)
    rid = "test-rid-123"
    r = client.get("/health", headers={"x-request-id": rid})
    assert r.status_code == 200
    assert r.headers.get("x-request-id") == rid
