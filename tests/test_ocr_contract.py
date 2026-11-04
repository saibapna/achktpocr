def test_models_endpoint_reports_unconfigured_models(client):
    response = client.get("/v1/models")
    assert response.status_code == 200
    assert response.json()["detector"]["status"] == "not_configured"


def test_invalid_upload_is_rejected_before_inference(client):
    response = client.post(
        "/v1/ocr/ktp",
        files={"file": ("not-an-image.jpg", b"not an image", "image/jpeg")},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_IMAGE"


def test_valid_upload_does_not_claim_ocr_success_without_models(client, valid_png):
    response = client.post(
        "/v1/ocr/ktp",
        files={"file": ("sample.png", valid_png, "image/png")},
    )
    assert response.status_code == 501
    assert response.json()["detail"]["code"] == "MODEL_NOT_CONFIGURED"
