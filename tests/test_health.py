def test_liveness(client):
    assert client.get("/health/live").json()["status"] == "alive"


def test_readiness_fails_when_runtime_missing(client, monkeypatch):
    monkeypatch.setattr("app.api.routes.health.engine_available", lambda: False)
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["reason"] == "MODEL_NOT_CONFIGURED"
