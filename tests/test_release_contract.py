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
    required = [
        "/ready", "/health", "/api/contract",
        "/student/assessments", "/student/assessments/results/history",
        "/notifications", "/student/access", "/student/payments/request",
        "/student/files", "/admin/notifications/broadcast", "/admin/agents",
        "/manager/payments", "/manager/assessments", "/manager/audit-log",
    ]
    live_routes = {route.path for route in app.routes if hasattr(route, "path")}
    assert all(path in live_routes for path in required)
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


def test_student_file_learning_cycle_is_wired():
    source = open("web/student-files.js", encoding="utf-8").read()
    for route in (
        "/student/files/upload",
        "/agent/teacher/",
        "/teaching-steps",
        "/understanding",
        "/confirm",
        "/file-exams/",
    ):
        assert route in source
    assert 'source:"student_files"' in source
    assert "تم إرسال النتيجة إلى المدير العام." in source

def test_readiness_is_database_backed(monkeypatch):
    from app.api import system

    class BrokenSession:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def execute(self, statement):
            raise RuntimeError("database unavailable")

    monkeypatch.setattr(system, "SessionLocal", lambda: BrokenSession())
    from fastapi.testclient import TestClient
    from app.main import app
    response = TestClient(app).get("/ready")
    assert response.status_code == 503
