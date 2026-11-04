import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.security import require_api_key
from app.main import app


@pytest.fixture
def client() -> TestClient:
    app.dependency_overrides[require_api_key] = lambda: None
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def valid_png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), color="white").save(buffer, format="PNG")
    return buffer.getvalue()
