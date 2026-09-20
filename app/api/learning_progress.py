"""Student and manager academic progress endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_db
from app.auth.authorization import require_owner_or_admin
from app.db.models import User
from app.agents.main_manager import MainManagerService
from app.db.progress_models import LearningWeakPoint
from app.db.curriculum_models import CurriculumCourse
from app.learning.progress_service import get_course_progress

router = APIRouter(prefix="/learning-progress", tags=["learning-progress"])


@router.get("/courses/{course_id}")
def course_progress(course_id: str, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    try:
        return get_course_progress(db, actor.id, course_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/courses")
def my_courses_progress(db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    courses = db.query(CurriculumCourse).filter(CurriculumCourse.is_active.is_(True)).order_by(CurriculumCourse.position).all()
    return {"courses": [get_course_progress(db, actor.id, c.id) for c in courses]}


@router.get("/manager/students/{user_id}")
def manager_student_progress(user_id: str, db: Session = Depends(get_db), _: list = Depends(require_owner_or_admin)):
    try:
        return MainManagerService.student_snapshot(db, user_id)["progress"]
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
