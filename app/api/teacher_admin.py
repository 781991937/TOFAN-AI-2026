"""Owner/admin API for creating and configuring AI teacher agents."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.models import Agent, AgentKind, AgentStatus
from app.agents.teacher import create_curriculum_teacher_agent, create_teacher_agent, provision_teacher_agents_for_curriculum, provision_teacher_agents_for_institution
from app.agents.teaching_policy import grant_paid_global_access
from app.auth.authorization import require_owner_or_admin
from app.auth.dependencies import get_db

router = APIRouter(prefix="/admin/teacher-agents", tags=["admin-teacher-agents"])


class TeacherCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str = Field(min_length=2, max_length=150)
    course_id: str = Field(min_length=1, max_length=36)
    description: str | None = Field(default=None, max_length=2000)
    teaching_language: str = Field(default="ar", min_length=2, max_length=20)


class CurriculumTeacherCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str = Field(min_length=2, max_length=150)
    curriculum_course_id: str = Field(min_length=1, max_length=36)
    description: str | None = Field(default=None, max_length=2000)
    teaching_language: str = Field(default="ar", min_length=2, max_length=20)


@router.post("/curriculum", status_code=201)
def create_curriculum_teacher(
    payload: CurriculumTeacherCreateRequest,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    try:
        agent = create_curriculum_teacher_agent(
            db,
            name=payload.name,
            slug=payload.slug,
            curriculum_course_id=payload.curriculum_course_id,
            description=payload.description,
            teaching_language=payload.teaching_language,
        )
        db.commit()
        db.refresh(agent)
        return {
            "id": agent.id,
            "name": agent.name,
            "slug": agent.slug,
            "kind": agent.kind.value,
            "status": agent.status.value,
            "curriculum_course_id": agent.curriculum_course_id,
        }
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/provision/curriculum/{curriculum_slug}")
def provision_curriculum_teachers(
    curriculum_slug: str,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    try:
        created = provision_teacher_agents_for_curriculum(db, curriculum_slug=curriculum_slug)
        db.commit()
        return {
            "curriculum_slug": curriculum_slug,
            "created_count": len(created),
            "agents": [
                {
                    "id": agent.id,
                    "name": agent.name,
                    "slug": agent.slug,
                    "curriculum_course_id": agent.curriculum_course_id,
                    "status": agent.status.value,
                }
                for agent in created
            ],
        }
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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



@router.post("/provision/institution/{institution_id}")
def provision_institution_teachers(
    institution_id: str,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    try:
        created = provision_teacher_agents_for_institution(
            db, institution_id=institution_id
        )
        db.commit()
        return {
            "institution_id": institution_id,
            "created_count": len(created),
            "agents": [
                {
                    "id": agent.id,
                    "name": agent.name,
                    "slug": agent.slug,
                    "course_id": agent.teacher_course_id,
                    "status": agent.status.value,
                }
                for agent in created
            ],
        }
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc



@router.post("/{agent_id}/access/{user_id}/global/grant")
def grant_global_paid_access(
    agent_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    agent = db.get(Agent, agent_id)
    if agent is None or agent.kind != AgentKind.TEACHER:
        raise HTTPException(status_code=404, detail="Teacher agent not found.")
    usage = grant_paid_global_access(db, user_id=user_id, agent_id=agent_id)
    db.commit()
    return {
        "agent_id": agent_id,
        "user_id": user_id,
        "paid_access": usage.paid_access,
        "global_curriculum": "full",
    }


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
            "curriculum_course_id": getattr(agent, "curriculum_course_id", None),
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
