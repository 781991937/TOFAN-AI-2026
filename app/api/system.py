"""System readiness and API contract endpoints."""
from fastapi import APIRouter, Request
from app.db.session import DATABASE_URL
import os

router = APIRouter(tags=["system"])

API_CONTRACT_VERSION = "2026-09-22.v1"

@router.get("/api/contract", tags=["system"])
def api_contract(request: Request):
    route_paths = {route.path for route in request.app.routes if hasattr(route, "path")}
    return {
        "contract_version": API_CONTRACT_VERSION,
        "base": "/",
        "authentication": "Bearer token/session supplied by the existing auth layer",
        "student": {
            "curriculum": "/curriculum/{slug}",
            "assessments": "/student/assessments",
            "assessment_results": "/student/assessments/results/history",
            "notifications": "/notifications",
            "access": "/student/access",
            "payments": "/student/payments/request",
            "progress": "/learning-progress/courses",
            "files": "/student/files",
        },
        "admin": {
            "notifications": "/admin/notifications/broadcast",
            "agents": "/admin/agents",
            "payments": "/manager/payments",
            "assessments": "/manager/assessments",
            "audit": "/manager/audit-log",
        },
        "data_path": "UI -> API -> database/services -> authorization -> persisted result",
        "database": "postgresql" if DATABASE_URL.startswith("postgresql") else "sqlite-development",
        "storage": "s3" if os.getenv("TOFAN_STORAGE_BACKEND", "local") == "s3" else "local-development",
        "security": {"baseline_headers": True},
        "route_count": len(route_paths),
        "required_routes_present": all(path in route_paths for path in ["/ready", "/health", "/api/contract", "/student/assessments", "/student/assessments/results/history", "/notifications"]),
    }

@router.get("/ready", tags=["system"])
def readiness():
    return {"status": "ready", "contract_version": API_CONTRACT_VERSION}
