"""Owner/admin API for creating and configuring AI teacher agents."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.models import Agent, AgentKind, AgentStatus
from app.agents.teacher import create_teacher_agent
from app.auth.authorization import require_owner_or_admin
from app.auth.dependencies import get_db

router = APIRouter(prefix="/admin/teacher-agents", tags=["admin-teacher-agents"])


class TeacherCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str = Field(min_length=2, max_length=150)
    course_id: str = Field(min_length=1, max_length=36)
    description: str | None = Field(default=None, max_length=2000)
    teaching_language: str = Field(default="ar", min_length=2, max_length=20)


@router.post("", status_code=201)
def create_teacher(
    payload: TeacherCreateRequest,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    try:
        agent = create_teacher_agent(
            db,
            name=payload.name,
            slug=payload.slug,
            course_id=payload.course_id,
            description=payload.description,
            teaching_language=payload.teaching_language,
        )
        agent.teacher_course_id = payload.course_id
        db.commit()
        db.refresh(agent)
        return {
            "id": agent.id,
            "name": agent.name,
            "slug": agent.slug,
            "kind": agent.kind.value,
            "status": agent.status.value,
            "course_id": payload.course_id,
        }
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("")
def list_teachers(
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    teachers = db.scalars(
        select(Agent).where(Agent.kind == AgentKind.TEACHER).order_by(Agent.created_at)
    ).all()
    return [
        {
            "id": agent.id,
            "name": agent.name,
            "slug": agent.slug,
            "status": agent.status.value,
            "course_id": getattr(agent, "teacher_course_id", None),
            "memory_enabled": agent.memory_enabled,
        }
        for agent in teachers
    ]


@router.patch("/{agent_id}/status")
def change_teacher_status(
    agent_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    agent = db.get(Agent, agent_id)
    if agent is None or agent.kind != AgentKind.TEACHER:
        raise HTTPException(status_code=404, detail="Teacher agent not found.")
    try:
        status = AgentStatus(str(payload.get("status")))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid agent status.") from exc
    agent.status = status
    db.commit()
    return {"id": agent.id, "status": agent.status.value}
