import os
import pytest
from fastapi.testclient import TestClient

def test_api_contract_and_readiness():
    os.environ["DATABASE_URL"] = "sqlite:///./release_contract.db"
    from app.main import app
    client = TestClient(app)
    contract = client.get("/api/contract")
    assert contract.status_code == 200
    body = contract.json()
    assert body["contract_version"]
    assert body["student"]["assessments"] == "/student/assessments"
    assert body["admin"]["agents"] == "/admin/agents"
    assert body["required_routes_present"] is True
    assert body["security"]["baseline_headers"] is True
    ready = client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"

def test_production_rejects_sqlite():
    source = open("app/db/session.py", encoding="utf-8").read()
    assert 'Production requires DATABASE_URL to point to PostgreSQL.' in source

def test_required_student_frontend_modules_are_referenced():
    html = open("web/index.html", encoding="utf-8").read()
    for module in ("app.js", "assessments.js", "student-files.js", "subscriptions.js"):
        assert module in html
