"""Main-manager administrative and observability endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.main_manager import MainManagerService
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
