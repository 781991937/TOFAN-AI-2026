"""Student-facing teaching access controls and mastery checkpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
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
from app.db.models import TeachingSource, User, TeachingStep, TeachingStepStatus
from app.db.curriculum_models import CurriculumCourse, CurriculumUnit, CurriculumLesson, CourseAssessment
from app.db.assessment_models import CurriculumAssessmentAttempt, AssessmentAttemptStatus, AssessmentResultReport
from app.db.assessment_question_models import CurriculumAssessmentQuestion
from app.agents.assessment_generator import generate_assessment_questions, grade_answers
from app.agents.llm import build_configured_provider
from datetime import datetime
import json

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


class CurriculumAssessmentSubmitRequest(BaseModel):
    answers: dict[str, str] = {}


@router.post("/{slug}/assessments/{assessment_id}/generate")
def generate_curriculum_assessment(
    slug: str,
    assessment_id: str,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    agent = _teacher(db, slug)
    assessment = db.get(CourseAssessment, assessment_id)
    if assessment is None or assessment.course_id != agent.curriculum_course_id:
        raise HTTPException(status_code=404, detail="Assessment not found for this teacher course.")
    existing = db.scalars(select(CurriculumAssessmentQuestion).where(
        CurriculumAssessmentQuestion.assessment_id == assessment.id
    ).order_by(CurriculumAssessmentQuestion.position)).all()
    if not existing:
        course = db.get(CurriculumCourse, agent.curriculum_course_id)
        if course is None:
            raise HTTPException(status_code=409, detail="Teacher course is unavailable.")
        try:
            questions = generate_assessment_questions(
                db=db,
                course=course,
                provider=build_configured_provider(),
                question_count=20,
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Assessment generation failed.") from exc
        for q in questions:
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
        existing = db.scalars(select(CurriculumAssessmentQuestion).where(
            CurriculumAssessmentQuestion.assessment_id == assessment.id
        ).order_by(CurriculumAssessmentQuestion.position)).all()
    return {
        "assessment_id": assessment.id,
        "title": assessment.title,
        "pass_percentage": assessment.pass_percentage,
        "question_count": len(existing),
        "questions": [
            {
                "id": q.id,
                "position": q.position,
                "type": q.question_type,
                "prompt": q.prompt,
                "options": json.loads(q.options_json),
                "points": q.points,
            }
            for q in existing
        ],
    }


@router.get("/{slug}/assessments/{assessment_id}/questions")
def get_curriculum_assessment_questions(
    slug: str,
    assessment_id: str,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    agent = _teacher(db, slug)
    assessment = db.get(CourseAssessment, assessment_id)
    if assessment is None or assessment.course_id != agent.curriculum_course_id:
        raise HTTPException(status_code=404, detail="Assessment not found for this teacher course.")
    rows = db.scalars(select(CurriculumAssessmentQuestion).where(
        CurriculumAssessmentQuestion.assessment_id == assessment.id
    ).order_by(CurriculumAssessmentQuestion.position)).all()
    if not rows:
        raise HTTPException(status_code=409, detail="Assessment has not been generated yet.")
    return {
        "assessment_id": assessment.id,
        "title": assessment.title,
        "pass_percentage": assessment.pass_percentage,
        "question_count": len(rows),
        "questions": [
            {
                "id": q.id,
                "position": q.position,
                "type": q.question_type,
                "prompt": q.prompt,
                "options": json.loads(q.options_json),
                "points": q.points,
            }
            for q in rows
        ],
    }


@router.post("/{slug}/assessments/{assessment_id}/submit")
def submit_curriculum_assessment(
    slug: str,
    assessment_id: str,
    payload: CurriculumAssessmentSubmitRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    agent = _teacher(db, slug)
    assessment = db.get(CourseAssessment, assessment_id)
    if assessment is None or assessment.course_id != agent.curriculum_course_id:
        raise HTTPException(status_code=404, detail="Assessment not found for this teacher course.")
    questions = db.scalars(select(CurriculumAssessmentQuestion).where(
        CurriculumAssessmentQuestion.assessment_id == assessment.id
    ).order_by(CurriculumAssessmentQuestion.position)).all()
    if not questions:
        raise HTTPException(status_code=409, detail="Generate the assessment before submitting answers.")
    if set(payload.answers) - {str(q.position) for q in questions}:
        raise HTTPException(status_code=400, detail="Unknown assessment question position.")
    score, max_score, details = grade_answers(questions, payload.answers)
    percentage = (score / max_score) * 100 if max_score else 0
    passed = assessment.pass_percentage is None or percentage >= assessment.pass_percentage
    attempt = CurriculumAssessmentAttempt(
        user_id=actor.id,
        agent_id=agent.id,
        assessment_id=assessment.id,
        status=AssessmentAttemptStatus.GRADED,
        score=score,
        max_score=max_score,
        percentage=percentage,
        passed=passed,
        answers_json=json.dumps(payload.answers, ensure_ascii=False),
        submitted_at=datetime.utcnow(),
        graded_at=datetime.utcnow(),
    )
    db.add(attempt)
    db.flush()
    report = AssessmentResultReport(attempt_id=attempt.id, status="pending")
    db.add(report)
    main_agent = db.scalar(select(Agent).where(
        Agent.slug == "tofan-main", Agent.kind == AgentKind.ORCHESTRATOR,
    ))
    if main_agent is not None:
        from app.db.models import AgentRun
        db.add(AgentRun(
            agent_id=main_agent.id,
            actor_user_id=actor.id,
            tool_name="education.curriculum_assessment_result",
            status="completed",
            input_text=f"curriculum_assessment:{attempt.id}",
            output_text=json.dumps({
                "attempt_id": attempt.id,
                "assessment_id": assessment.id,
                "student_id": actor.id,
                "teacher_agent_id": agent.id,
                "score": score,
                "max_score": max_score,
                "percentage": percentage,
                "passed": passed,
            }, ensure_ascii=False),
            completed_at=datetime.utcnow(),
        ))
    db.commit()
    return {
        "attempt_id": attempt.id,
        "assessment_id": assessment.id,
        "score": score,
        "max_score": max_score,
        "percentage": round(percentage, 2),
        "passed": passed,
        "details": details,
        "manager_report": "submitted_to_tofan_main",
    }


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


def _curriculum_steps(db: Session, agent: Agent):
    if not agent.curriculum_course_id:
        return []
    units = db.scalars(select(CurriculumUnit).where(
        CurriculumUnit.course_id == agent.curriculum_course_id
    ).order_by(CurriculumUnit.position)).all()
    steps = []
    position = 1
    for unit in units:
        lessons = db.scalars(select(CurriculumLesson).where(
            CurriculumLesson.unit_id == unit.id
        ).order_by(CurriculumLesson.position)).all()
        for lesson in lessons:
            steps.append({
                "position": position,
                "unit_id": unit.id,
                "unit_position": unit.position,
                "unit_title": unit.title,
                "lesson_id": lesson.id,
                "lesson_position": lesson.position,
                "lesson_title": lesson.title,
                "scope_key": f"course:{agent.curriculum_course_id}:unit:{unit.id}:lesson:{lesson.id}",
            })
            position += 1
    return steps


@router.get("/{slug}/progress")
def curriculum_progress(
    slug: str,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    agent = _teacher(db, slug)
    course = db.get(CurriculumCourse, agent.curriculum_course_id) if agent.curriculum_course_id else None
    if course is None:
        raise HTTPException(status_code=409, detail="This teacher is not assigned to a TOFAN curriculum course.")
    plan = _curriculum_steps(db, agent)
    stored = db.scalars(select(TeachingStep).where(
        TeachingStep.user_id == actor.id,
        TeachingStep.agent_id == agent.id,
        TeachingStep.source == TeachingSource.GLOBAL_CURRICULUM,
    )).all()
    by_position = {step.position: step for step in stored}
    completed = sum(
        1 for item in plan
        if by_position.get(item["position"]) and by_position[item["position"]].status == TeachingStepStatus.COMPLETED
    )
    current = next(
        (item for item in plan if not (
            by_position.get(item["position"]) and
            by_position[item["position"]].status == TeachingStepStatus.COMPLETED
        )),
        None,
    )
    if current and current["position"] in by_position:
        step = by_position[current["position"]]
        current = {
            **current,
            "status": step.status,
            "attempts": step.attempts,
            "understanding_verified": step.understanding_verified,
            "student_confirmed": step.student_confirmed,
        }
    return {
        "course": {"id": course.id, "code": course.code, "name": course.name},
        "total_steps": len(plan),
        "completed_steps": completed,
        "progress_percentage": round((completed / len(plan)) * 100, 2) if plan else 0,
        "current_step": current,
        "course_completed": bool(plan) and completed == len(plan),
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
        if agent.curriculum_course_id and payload.source == TeachingSource.GLOBAL_CURRICULUM:
            plan = _curriculum_steps(db, agent)
            expected = next((item for item in plan if item["position"] == payload.position), None)
            if expected is None or expected["scope_key"] != payload.scope_key:
                raise HTTPException(status_code=409, detail="Invalid curriculum step. The teacher can only open a real TOFAN lesson step.")
            completed_positions = {
                s.position for s in db.scalars(select(TeachingStep).where(
                    TeachingStep.user_id == actor.id,
                    TeachingStep.agent_id == agent.id,
                    TeachingStep.source == TeachingSource.GLOBAL_CURRICULUM,
                    TeachingStep.status == TeachingStepStatus.COMPLETED,
                )).all()
            }
            if payload.position > 1 and any(p not in completed_positions for p in range(1, payload.position)):
                raise HTTPException(status_code=409, detail="You must complete the previous lesson step before advancing.")
        step = start_step(
            db, user_id=actor.id, agent_id=agent.id, source=payload.source,
            scope_key=payload.scope_key, position=payload.position,
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
