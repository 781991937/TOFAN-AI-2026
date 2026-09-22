import time

from fastapi.testclient import TestClient

from app.main import app


def test_readiness_smoke_latency():
    client = TestClient(app)
    started = time.perf_counter()
    for _ in range(20):
        response = client.get("/ready")
        assert response.status_code == 200
    elapsed = time.perf_counter() - started
    assert elapsed < 3.0
