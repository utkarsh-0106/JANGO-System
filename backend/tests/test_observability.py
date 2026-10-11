from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_request_id_is_returned_and_can_be_provided():
    response = client.get("/api/health", headers={"X-Request-ID": "test-request-123"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request-123"


def test_request_id_is_generated_when_missing():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
