"""Student-facing teaching access controls and mastery checkpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.models import Agent, AgentKind, AgentStatus
from app.agents.teaching_policy import (
    TeachingAccessError,
    confirm_student_understanding,
    get_or_create_usage,
    remaining_response_chars,
    record_understanding_check,
    record_exam_result,
    start_step,
)
from app.auth.dependencies import get_current_user, get_db
from app.db.models import TeachingSource, User

router = APIRouter(prefix="/agent/teacher", tags=["teacher-teaching-policy"])


def _teacher(db: Session, slug: str) -> Agent:
    agent = db.query(Agent).filter(
        Agent.slug == slug,
        Agent.kind == AgentKind.TEACHER,
        Agent.status == AgentStatus.ACTIVE,
    ).first()
    if agent is None:
        raise HTTPException(status_code=404, detail="Active teacher agent not found.")
    return agent


class StartStepRequest(BaseModel):
    source: TeachingSource
    scope_key: str
    position: int


class UnderstandingRequest(BaseModel):
    verified: bool


class ConfirmationRequest(BaseModel):
    confirmed: bool


class ExamResultRequest(BaseModel):
    content_file_id: str
    score: float
    max_score: float
    passed: bool


@router.get("/{slug}/teaching-access")
def teaching_access(
    slug: str,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    agent = _teacher(db, slug)
    global_usage = get_or_create_usage(
        db, user_id=actor.id, agent_id=agent.id, source=TeachingSource.GLOBAL_CURRICULUM
    )
    student_usage = get_or_create_usage(
        db, user_id=actor.id, agent_id=agent.id, source=TeachingSource.STUDENT_FILES
    )
    return {
        "teacher_agent_id": agent.id,
        "student_files": {
            "limit": 3,
            "policy": "three student-uploaded files; no step-based quota",
            "used": student_usage.files_used,
            "remaining": max(0, student_usage.files_limit - student_usage.files_used),
        },
        "student_file_responses": {
            "limit": student_usage.response_chars_limit,
            "used": student_usage.response_chars_used,
            "remaining": remaining_response_chars(
                db, user_id=actor.id, agent_id=agent.id,
                source=TeachingSource.STUDENT_FILES,
            ),
        },
        "global_curriculum": {
            "response_chars_limit": global_usage.response_chars_limit,
            "response_chars_used": global_usage.response_chars_used,
            "response_chars_remaining": remaining_response_chars(
                db, user_id=actor.id, agent_id=agent.id,
                source=TeachingSource.GLOBAL_CURRICULUM,
            ),
            "paid_access": global_usage.paid_access,
        },
        "mastery_rule": (
            "A step is complete only after teacher verification of understanding "
            "and explicit student confirmation."
        ),
    }



@router.post("/{slug}/file-exams")
def submit_file_exam(
    slug: str,
    payload: ExamResultRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    agent = _teacher(db, slug)
    try:
        result = record_exam_result(
            db,
            user_id=actor.id,
            agent_id=agent.id,
            content_file_id=payload.content_file_id,
            score=payload.score,
            max_score=payload.max_score,
            passed=payload.passed,
        )
        db.commit()
        return {
            "assessment_id": result.id,
            "score": result.score,
            "max_score": result.max_score,
            "percentage": result.percentage,
            "passed": result.passed,
            "file_cycle_completed": True,
            "manager_report": "submitted_to_tofan_main",
        }
    except TeachingAccessError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{slug}/teaching-steps")
def begin_step(
    slug: str,
    payload: StartStepRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    agent = _teacher(db, slug)
    try:
        step = start_step(
            db,
            user_id=actor.id,
            agent_id=agent.id,
            source=payload.source,
            scope_key=payload.scope_key,
            position=payload.position,
        )
        db.commit()
        return {
            "id": step.id,
            "source": step.source,
            "scope_key": step.scope_key,
            "position": step.position,
            "status": step.status,
            "attempts": step.attempts,
            "understanding_verified": step.understanding_verified,
            "student_confirmed": step.student_confirmed,
        }
    except TeachingAccessError as exc:
        db.rollback()
        raise HTTPException(status_code=402, detail=str(exc)) from exc


@router.post("/{slug}/teaching-steps/{step_id}/understanding")
def understanding_check(
    slug: str,
    step_id: str,
    payload: UnderstandingRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    agent = _teacher(db, slug)
    try:
        from app.db.models import TeachingStep
        step = db.get(TeachingStep, step_id)
        if step is None or step.agent_id != agent.id or step.user_id != actor.id:
            raise HTTPException(status_code=404, detail="Teaching step not found.")
        step = record_understanding_check(db, step_id=step_id, verified=payload.verified)
        db.commit()
        return {
            "id": step.id,
            "attempts": step.attempts,
            "understanding_verified": step.understanding_verified,
            "status": step.status,
        }
    except HTTPException:
        db.rollback()
        raise
    except TeachingAccessError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{slug}/teaching-steps/{step_id}/confirm")
def confirm_step(
    slug: str,
    step_id: str,
    payload: ConfirmationRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    agent = _teacher(db, slug)
    try:
        from app.db.models import TeachingStep
        step = db.get(TeachingStep, step_id)
        if step is None or step.agent_id != agent.id or step.user_id != actor.id:
            raise HTTPException(status_code=404, detail="Teaching step not found.")
        step = confirm_student_understanding(
            db, step_id=step_id, confirmed=payload.confirmed
        )
        db.commit()
        return {
            "id": step.id,
            "status": step.status,
            "understanding_verified": step.understanding_verified,
            "student_confirmed": step.student_confirmed,
            "completed": step.status == "completed",
        }
    except HTTPException:
        db.rollback()
        raise
    except TeachingAccessError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
