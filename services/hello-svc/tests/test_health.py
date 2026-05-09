from fastapi.testclient import TestClient

from hello_svc.main import app


def test_health_returns_ok(env_settings):
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
