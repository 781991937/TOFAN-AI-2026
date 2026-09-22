"""Main-manager administrative and observability endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.agents.main_manager import MainManagerService
from app.agents.models import AgentStatus
from app.auth.authorization import require_owner_or_admin
from app.auth.dependencies import get_db
from app.db.models import User
from app.db.identity_models import PaymentStatus

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


@router.get("/courses")
def manager_courses(
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    return MainManagerService.courses(db)


@router.post("/payments/{transaction_id}/confirm")
def confirm_payment(
    transaction_id: str,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    from app.agents.payment_tools import confirm_payment_transaction
    try:
        return confirm_payment_transaction(db, transaction_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/payments/{transaction_id}/reject")
def reject_payment(
    transaction_id: str,
    reason: str | None = None,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    from app.db.identity_models import PaymentTransaction
    transaction = db.get(PaymentTransaction, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Payment transaction not found.")
    if transaction.status != PaymentStatus.PENDING:
        raise HTTPException(status_code=409, detail="Only pending payment transactions can be rejected.")
    transaction.status = PaymentStatus.REJECTED
    transaction.rejection_reason = reason
    db.commit()
    return {
        "transaction_id": transaction.id,
        "status": transaction.status,
        "reason": transaction.rejection_reason,
    }


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
def manager_students(query: str | None = Query(None, max_length=100), limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), db: Session = Depends(get_db), _: list = Depends(require_owner_or_admin)):
    return MainManagerService.students(db, limit=limit, offset=offset, query=query)

@router.get("/assessments")
def manager_assessments(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), db: Session = Depends(get_db), _: list = Depends(require_owner_or_admin)):
    return MainManagerService.assessments(db, limit=limit, offset=offset)

@router.get("/payments")
def manager_payments(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), db: Session = Depends(get_db), _: list = Depends(require_owner_or_admin)):
    return MainManagerService.payments(db, limit=limit, offset=offset)

@router.get("/audit-log")
def manager_audit_log(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), db: Session = Depends(get_db), _: list = Depends(require_owner_or_admin)):
    return MainManagerService.audit_log(db, limit=limit, offset=offset)
