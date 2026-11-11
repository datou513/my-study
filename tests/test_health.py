from fastapi.testclient import TestClient

from src.api.main import app


def test_health_is_ok() -> None:
    with TestClient(app) as client:
        r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
