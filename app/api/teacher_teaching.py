"""Student-facing teaching access controls and mastery checkpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.models import Agent, AgentKind, AgentStatus
from app.agents.teaching_policy import (
    TeachingAccessError,
    confirm_student_understanding,
    global_free_access_remaining,
    record_understanding_check,
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


@router.get("/{slug}/teaching-access")
def teaching_access(
    slug: str,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    agent = _teacher(db, slug)
    return {
        "teacher_agent_id": agent.id,
        "student_files": {
            "limit": 3,
            "policy": "three student-uploaded files; no step-based quota",
        },
        "global_curriculum": {
            "free_steps_limit": 5,
            "free_steps_remaining": global_free_access_remaining(
                db, user_id=actor.id, agent_id=agent.id
            ),
            "paid_access": False,
        },
        "mastery_rule": (
            "A step is complete only after teacher verification of understanding "
            "and explicit student confirmation."
        ),
    }


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
