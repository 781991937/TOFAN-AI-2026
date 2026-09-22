"""Student-facing curriculum assessment API.

Keeps the assessment lifecycle in one place:
discover -> generate -> answer -> grade -> persist -> report -> analyze.
"""

from datetime import datetime
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_db
from app.db.models import User
from app.db.curriculum_models import CurriculumCourse, CourseAssessment
from app.db.assessment_models import CurriculumAssessmentAttempt, AssessmentAttemptStatus
from app.db.assessment_question_models import CurriculumAssessmentQuestion
from app.agents.models import Agent, AgentKind, AgentStatus
from app.agents.assessment_generator import generate_assessment_questions, grade_answers
from app.agents.llm import build_configured_provider
from app.agents.main_manager import MainManagerService
from app.learning.progress_service import record_assessment_progress, get_course_progress
from app.agents.academy_access_policy import has_curriculum_stage_access

router = APIRouter(prefix="/student/assessments", tags=["student-assessments"])


class SubmitRequest(BaseModel):
    answers: dict[str, str] = Field(default_factory=dict)


def _assessment(db: Session, assessment_id: str):
    row = db.get(CourseAssessment, assessment_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Assessment not found.")
    course = db.get(CurriculumCourse, row.course_id)
    if course is None or not course.is_active:
        raise HTTPException(status_code=404, detail="Assessment course is unavailable.")
    return row, course


def _can_access(db: Session, user_id: str, course: CurriculumCourse) -> bool:
    return has_curriculum_stage_access(db, user_id=user_id, stage_id=course.stage_id)


def _serialize_question(q):
    return {
        "id": q.id,
        "position": q.position,
        "type": q.question_type,
        "prompt": q.prompt,
        "options": json.loads(q.options_json),
        "points": q.points,
    }


@router.get("")
def list_assessments(db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    rows = db.scalars(
        select(CourseAssessment).join(CurriculumCourse).where(CurriculumCourse.is_active.is_(True))
        .order_by(CurriculumCourse.position, CourseAssessment.title)
    ).all()
    result = []
    for a in rows:
        course = db.get(CurriculumCourse, a.course_id)
        if course is None or not _can_access(db, actor.id, course):
            continue
        latest = db.scalar(
            select(CurriculumAssessmentAttempt)
            .where(
                CurriculumAssessmentAttempt.user_id == actor.id,
                CurriculumAssessmentAttempt.assessment_id == a.id,
            )
            .order_by(desc(CurriculumAssessmentAttempt.started_at))
        )
        result.append({
            "assessment_id": a.id,
            "course_id": course.id,
            "course_name": course.name,
            "course_code": course.code,
            "title": a.title,
            "description": a.description,
            "pass_percentage": a.pass_percentage,
            "latest": None if latest is None else {
                "attempt_id": latest.id,
                "percentage": latest.percentage,
                "passed": latest.passed,
                "graded_at": latest.graded_at.isoformat() if latest.graded_at else None,
            },
        })
    return {"assessments": result}


@router.get("/{assessment_id}")
def get_assessment(
    assessment_id: str,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    assessment, course = _assessment(db, assessment_id)
    if not _can_access(db, actor.id, course):
        raise HTTPException(status_code=403, detail="Assessment access is not enabled for this stage.")
    questions = db.scalars(
        select(CurriculumAssessmentQuestion)
        .where(CurriculumAssessmentQuestion.assessment_id == assessment.id)
        .order_by(CurriculumAssessmentQuestion.position)
    ).all()
    return {
        "assessment_id": assessment.id,
        "course_id": course.id,
        "course_name": course.name,
        "title": assessment.title,
        "description": assessment.description,
        "pass_percentage": assessment.pass_percentage,
        "question_count": len(questions),
        "questions": [_serialize_question(q) for q in questions],
    }


@router.post("/{assessment_id}/generate")
def generate_assessment(
    assessment_id: str,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    assessment, course = _assessment(db, assessment_id)
    if not _can_access(db, actor.id, course):
        raise HTTPException(status_code=403, detail="Assessment access is not enabled for this stage.")
    questions = db.scalars(
        select(CurriculumAssessmentQuestion)
        .where(CurriculumAssessmentQuestion.assessment_id == assessment.id)
        .order_by(CurriculumAssessmentQuestion.position)
    ).all()
    if not questions:
        try:
            generated = generate_assessment_questions(
                db=db, course=course, provider=build_configured_provider(), question_count=20
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Assessment generation failed.") from exc
        for q in generated:
            db.add(CurriculumAssessmentQuestion(
                assessment_id=assessment.id,
                position=q.position,
                question_type=q.question_type,
                prompt=q.prompt,
                options_json=json.dumps(q.options, ensure_ascii=False),
                correct_answer=q.correct_answer,
                explanation=q.explanation,
                points=q.points,
            ))
        db.commit()
        questions = db.scalars(
            select(CurriculumAssessmentQuestion)
            .where(CurriculumAssessmentQuestion.assessment_id == assessment.id)
            .order_by(CurriculumAssessmentQuestion.position)
        ).all()
    return {
        "assessment_id": assessment.id,
        "title": assessment.title,
        "pass_percentage": assessment.pass_percentage,
        "question_count": len(questions),
        "questions": [_serialize_question(q) for q in questions],
    }


@router.post("/{assessment_id}/submit")
def submit_assessment(
    assessment_id: str,
    payload: SubmitRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    assessment, course = _assessment(db, assessment_id)
    if not _can_access(db, actor.id, course):
        raise HTTPException(status_code=403, detail="Assessment access is not enabled for this stage.")
    questions = db.scalars(
        select(CurriculumAssessmentQuestion)
        .where(CurriculumAssessmentQuestion.assessment_id == assessment.id)
        .order_by(CurriculumAssessmentQuestion.position)
    ).all()
    if not questions:
        raise HTTPException(status_code=409, detail="Generate the assessment before submitting.")
    expected = {str(q.position) for q in questions}
    if set(payload.answers) != expected:
        raise HTTPException(status_code=400, detail="Answer every assessment question before submitting.")

    teacher = db.scalar(
        select(Agent).where(
            Agent.kind == AgentKind.TEACHER,
            Agent.curriculum_course_id == course.id,
            Agent.status == AgentStatus.ACTIVE,
        ).order_by(Agent.created_at)
    )
    if teacher is None:
        raise HTTPException(status_code=409, detail="The course teacher is not active yet.")

    score, max_score, details = grade_answers(questions, payload.answers)
    percentage = (score / max_score * 100) if max_score else 0
    passed = assessment.pass_percentage is None or percentage >= assessment.pass_percentage
    now = datetime.utcnow()
    attempt = CurriculumAssessmentAttempt(
        user_id=actor.id, agent_id=teacher.id, assessment_id=assessment.id,
        status=AssessmentAttemptStatus.GRADED, score=score, max_score=max_score,
        percentage=percentage, passed=passed, answers_json=json.dumps(payload.answers, ensure_ascii=False),
        submitted_at=now, graded_at=now,
    )
    db.add(attempt)
    db.flush()
    record_assessment_progress(
        db, user_id=actor.id, course_id=course.id, percentage=percentage, passed=passed
    )
    MainManagerService.process_event(
        db, "education.curriculum_assessment_result", actor.id,
        {"resource_type": "curriculum_assessment_attempt", "resource_id": attempt.id,
         "attempt_id": attempt.id, "assessment_id": assessment.id, "student_id": actor.id,
         "teacher_agent_id": teacher.id, "score": score, "max_score": max_score,
         "percentage": percentage, "passed": passed},
    )
    return {
        "attempt_id": attempt.id, "assessment_id": assessment.id,
        "score": score, "max_score": max_score, "percentage": round(percentage, 2),
        "passed": passed, "details": details,
        "analysis": get_course_progress(db, actor.id, course.id),
    }


@router.get("/results/history")
def assessment_history(db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    rows = db.scalars(
        select(CurriculumAssessmentAttempt)
        .where(CurriculumAssessmentAttempt.user_id == actor.id)
        .order_by(desc(CurriculumAssessmentAttempt.started_at))
    ).all()
    return {"results": [
        {
            "attempt_id": r.id, "assessment_id": r.assessment_id, "score": r.score,
            "max_score": r.max_score, "percentage": r.percentage, "passed": r.passed,
            "status": r.status, "started_at": r.started_at.isoformat(),
            "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
            "graded_at": r.graded_at.isoformat() if r.graded_at else None,
        } for r in rows
    ]}
