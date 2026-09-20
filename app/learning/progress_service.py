"""Service for durable course/lesson progress, weak points, and next learning step."""

from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.curriculum_models import CurriculumCourse, CurriculumLesson, CurriculumUnit
from app.db.models import TeachingStep, TeachingStepStatus, TeachingSource
from app.db.progress_models import LearningProgress, LearningWeakPoint, LearningNextStep


def sync_lesson_progress(db: Session, user_id: str, agent_id: str, step: TeachingStep) -> None:
    if step.source != TeachingSource.GLOBAL_CURRICULUM or "course:" not in step.scope_key:
        return
    course_id = step.scope_key.split("course:", 1)[1].split(":unit:", 1)[0]
    lesson_id = None
    if ":lesson:" in step.scope_key:
        lesson_id = step.scope_key.split(":lesson:", 1)[1]
    if not lesson_id:
        return
    row = db.scalar(select(LearningProgress).where(
        LearningProgress.user_id == user_id,
        LearningProgress.course_id == course_id,
        LearningProgress.lesson_id == lesson_id,
    ))
    if row is None:
        row = LearningProgress(user_id=user_id, course_id=course_id, lesson_id=lesson_id)
        db.add(row)
    row.attempts = step.attempts
    row.understanding_verified = step.understanding_verified
    row.status = "completed" if step.status == TeachingStepStatus.COMPLETED else "in_progress"
    row.completed_at = step.completed_at if step.status == TeachingStepStatus.COMPLETED else None
    row.updated_at = datetime.utcnow()
    _recalculate_next_step(db, user_id, course_id)


def record_assessment_progress(
    db: Session, *, user_id: str, course_id: str, percentage: float,
    lesson_id: str | None = None, passed: bool = False,
) -> None:
    row = db.scalar(select(LearningProgress).where(
        LearningProgress.user_id == user_id,
        LearningProgress.course_id == course_id,
        LearningProgress.lesson_id == lesson_id,
    )) if lesson_id else None
    if row is not None:
        row.assessment_percentage = percentage
        row.last_score = percentage
        row.status = "completed" if passed else "remediation"
        if passed:
            row.completed_at = row.completed_at or datetime.utcnow()
    if not passed and lesson_id:
        weak = db.scalar(select(LearningWeakPoint).where(
            LearningWeakPoint.user_id == user_id,
            LearningWeakPoint.course_id == course_id,
            LearningWeakPoint.lesson_id == lesson_id,
            LearningWeakPoint.topic == "assessment",
        ))
        if weak is None:
            weak = LearningWeakPoint(user_id=user_id, course_id=course_id, lesson_id=lesson_id,
                                     topic="assessment", reason=f"Assessment score {percentage:.2f}%")
            db.add(weak)
        else:
            weak.occurrences += 1
            weak.reason = f"Assessment score {percentage:.2f}%"
            weak.last_seen_at = datetime.utcnow()
    _recalculate_next_step(db, user_id, course_id)


def _recalculate_next_step(db: Session, user_id: str, course_id: str) -> None:
    rows = db.scalars(select(LearningProgress).where(
        LearningProgress.user_id == user_id,
        LearningProgress.course_id == course_id,
    )).all()
    current = next((r for r in sorted(rows, key=lambda x: (x.lesson_id or "")) if r.status != "completed"), None)
    weak = db.scalars(select(LearningWeakPoint).where(
        LearningWeakPoint.user_id == user_id,
        LearningWeakPoint.course_id == course_id,
        LearningWeakPoint.resolved.is_(False),
    ).order_by(LearningWeakPoint.occurrences.desc())).all()
    nxt = db.scalar(select(LearningNextStep).where(
        LearningNextStep.user_id == user_id, LearningNextStep.course_id == course_id
    ))
    if nxt is None:
        nxt = LearningNextStep(user_id=user_id, course_id=course_id, action="continue",
                               reason="Continue to the next uncompleted lesson.", priority=1)
        db.add(nxt)
    if weak:
        nxt.action = "remediate"
        nxt.lesson_id = weak[0].lesson_id
        nxt.reason = f"Remediate weak point: {weak[0].topic}."
        nxt.priority = 1
    elif current:
        nxt.action = "continue"
        nxt.lesson_id = current.lesson_id
        nxt.reason = "Continue with the next uncompleted lesson."
        nxt.priority = 2
    else:
        nxt.action = "course_complete"
        nxt.lesson_id = None
        nxt.reason = "All tracked lessons are completed."
        nxt.priority = 3
    nxt.updated_at = datetime.utcnow()


def get_course_progress(db: Session, user_id: str, course_id: str) -> dict:
    course = db.get(CurriculumCourse, course_id)
    if course is None:
        raise ValueError("Course not found.")
    rows = db.scalars(select(LearningProgress).where(
        LearningProgress.user_id == user_id, LearningProgress.course_id == course_id
    )).all()
    total = db.scalar(select(CurriculumLesson.id).join(CurriculumUnit, CurriculumUnit.id == CurriculumLesson.unit_id)
                      .where(CurriculumUnit.course_id == course_id).count()) if False else None
    completed = sum(r.status == "completed" for r in rows)
    next_step = db.scalar(select(LearningNextStep).where(
        LearningNextStep.user_id == user_id, LearningNextStep.course_id == course_id
    ))
    weak = db.scalars(select(LearningWeakPoint).where(
        LearningWeakPoint.user_id == user_id, LearningWeakPoint.course_id == course_id,
        LearningWeakPoint.resolved.is_(False)
    ).order_by(LearningWeakPoint.occurrences.desc())).all()
    return {
        "course": {"id": course.id, "code": course.code, "name": course.name},
        "tracked_lessons": len(rows),
        "completed_lessons": completed,
        "progress_percentage": round((completed / len(rows)) * 100, 2) if rows else 0,
        "weak_points": [{"id": w.id, "topic": w.topic, "reason": w.reason, "severity": w.severity,
                         "occurrences": w.occurrences, "lesson_id": w.lesson_id} for w in weak],
        "next_step": None if next_step is None else {
            "action": next_step.action, "lesson_id": next_step.lesson_id,
            "reason": next_step.reason, "priority": next_step.priority
        },
        "lessons": [{
            "lesson_id": r.lesson_id, "status": r.status, "attempts": r.attempts,
            "understanding_verified": r.understanding_verified,
            "assessment_percentage": r.assessment_percentage,
            "last_score": r.last_score,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        } for r in rows],
    }
