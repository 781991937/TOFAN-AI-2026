from fastapi.testclient import TestClient

from app.main import app


def test_security_headers_are_present():
    client = TestClient(app)
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "geolocation=()" in response.headers["permissions-policy"]
