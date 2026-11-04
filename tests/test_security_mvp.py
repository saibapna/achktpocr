from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app


def test_ocr_requires_api_key(monkeypatch, valid_png):
    monkeypatch.setattr("app.core.security.get_settings", lambda: Settings(api_key="example-test-key"))
    with TestClient(app) as client:
        response = client.post(
            "/v1/ocr/ktp", files={"file": ("fixture.png", valid_png, "image/png")}
        )
        assert response.status_code == 401
        response = client.post(
            "/v1/ocr/ktp",
            files={"file": ("fixture.png", valid_png, "image/png")},
            headers={"X-API-Key": "not-the-key"},
        )
        assert response.status_code == 401


def test_ocr_rejects_unconfigured_auth(monkeypatch, valid_png):
    monkeypatch.setattr("app.core.security.get_settings", lambda: Settings(api_key=None))
    with TestClient(app) as client:
        response = client.post(
            "/v1/ocr/ktp", files={"file": ("fixture.png", valid_png, "image/png")}
        )
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "AUTH_NOT_CONFIGURED"
