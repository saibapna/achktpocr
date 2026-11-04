def test_liveness(client):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


def test_readiness_reports_model_not_configured(client):
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["reason"] == "MODEL_NOT_CONFIGURED"
