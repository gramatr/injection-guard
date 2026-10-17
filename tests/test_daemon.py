from fastapi.testclient import TestClient

from injection_guard import config, model
from injection_guard.daemon import app


def setup_module():
    model.load_model()


def test_health():
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["model_loaded"] is True


def test_classify_no_auth_required_by_default():
    assert config.AUTH_TOKEN is None, "test assumes no auth token set in env"
    with TestClient(app) as client:
        resp = client.post("/classify", json={"text": "hello"})
        assert resp.status_code == 200
        body = resp.json()
        assert "malicious" in body and "label" in body and "score" in body


def test_classify_rejects_bad_token_when_auth_enabled(monkeypatch):
    monkeypatch.setattr(config, "AUTH_TOKEN", "secret123")
    with TestClient(app) as client:
        resp = client.post(
            "/classify",
            json={"text": "hello"},
            headers={"Authorization": "Bearer wrong"},
        )
        assert resp.status_code == 401
