"""Main-manager administrative and observability endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.agents.main_manager import MainManagerService
from app.agents.models import AgentStatus
from app.auth.authorization import require_owner_or_admin
from app.auth.dependencies import get_db
from app.db.models import User

router = APIRouter(prefix="/manager", tags=["main-manager"])


@router.get("/status")
def manager_status(
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    try:
        manager = MainManagerService.get_manager(db)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "slug": manager.slug,
        "name": manager.name,
        "kind": manager.kind,
        "status": manager.status,
        "authority": [
            "payments",
            "assessment_results",
            "student_progress",
            "teacher_agent_oversight",
        ],
    }


@router.get("/students/{user_id}/snapshot")
def student_snapshot(
    user_id: str,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    try:
        return MainManagerService.student_snapshot(db, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/teachers")
def teacher_overview(
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    return {"teachers": MainManagerService.teacher_overview(db)}


@router.post("/teachers/{curriculum_course_id}/provision")
def provision_teacher(
    curriculum_course_id: str,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    try:
        return MainManagerService.provision_teacher(db, curriculum_course_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/teachers/{agent_id}/status")
def set_teacher_status(
    agent_id: str,
    status: AgentStatus,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    try:
        return MainManagerService.set_teacher_status(db, agent_id, status)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

@router.get("/dashboard")
def manager_dashboard(db: Session = Depends(get_db), _: list = Depends(require_owner_or_admin)):
    return MainManagerService.dashboard_summary(db)

@router.get("/students")
def manager_students(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), db: Session = Depends(get_db), _: list = Depends(require_owner_or_admin)):
    return MainManagerService.students(db, limit=limit, offset=offset)

@router.get("/assessments")
def manager_assessments(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), db: Session = Depends(get_db), _: list = Depends(require_owner_or_admin)):
    return MainManagerService.assessments(db, limit=limit, offset=offset)

@router.get("/payments")
def manager_payments(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), db: Session = Depends(get_db), _: list = Depends(require_owner_or_admin)):
    return MainManagerService.payments(db, limit=limit, offset=offset)

@router.get("/audit-log")
def manager_audit_log(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), db: Session = Depends(get_db), _: list = Depends(require_owner_or_admin)):
    return MainManagerService.audit_log(db, limit=limit, offset=offset)
