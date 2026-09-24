"""TOFAN teaching quotas, exams, and mastery policy."""

from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    ContentFile,
    TeachingAssessment,
    TeachingAssessmentReport,
    TeachingSource,
    TeachingStep,
    TeachingStepStatus,
    TeachingUsage,
)

class TeachingAccessError(ValueError):
    pass

STUDENT_FILE_LIMIT = 3
DAILY_RESPONSE_CHAR_LIMIT = 2000
PAID_GLOBAL_RESPONSE_CHAR_LIMIT = 2000


def get_or_create_usage(db: Session, user_id: str, agent_id: str, source: TeachingSource) -> TeachingUsage:
    usage = db.scalar(select(TeachingUsage).where(
        TeachingUsage.user_id == user_id,
        TeachingUsage.agent_id == agent_id,
        TeachingUsage.source == source,
    ))
    if usage is None:
        usage = TeachingUsage(
            user_id=user_id, agent_id=agent_id, source=source,
            files_limit=STUDENT_FILE_LIMIT,
            response_chars_limit=DAILY_RESPONSE_CHAR_LIMIT,
        )
        db.add(usage)
        db.flush()
    _reset_if_expired(usage)
    return usage


def _reset_if_expired(usage: TeachingUsage) -> None:
    now = datetime.utcnow()
    if usage.quota_started_at is None:
        usage.quota_started_at = now
        return
    if now >= usage.quota_started_at + timedelta(hours=24):
        usage.quota_started_at = now
        usage.files_used = 0
        usage.response_chars_used = 0
        usage.free_steps_used = 0


def register_student_file(db: Session, *, user_id: str, agent_id: str, content_file: ContentFile) -> TeachingUsage:
    usage = get_or_create_usage(db, user_id, agent_id, TeachingSource.STUDENT_FILES)
    if usage.files_used >= STUDENT_FILE_LIMIT:
        raise TeachingAccessError("The free student-file limit of 3 files for this 24-hour window has been reached.")
    usage.files_used += 1
    content_file.uploaded_by_user_id = user_id
    content_file.teaching_source = TeachingSource.STUDENT_FILES
    db.flush()
    return usage


def remaining_response_chars(db: Session, *, user_id: str, agent_id: str, source: TeachingSource) -> int | None:
    usage = get_or_create_usage(db, user_id, agent_id, source)
    if source == TeachingSource.GLOBAL_CURRICULUM and usage.paid_access:
        return None
    return max(0, usage.response_chars_limit - usage.response_chars_used)


def consume_response_chars(db: Session, *, user_id: str, agent_id: str, source: TeachingSource, characters: int) -> int | None:
    if characters < 0:
        raise TeachingAccessError("Character usage cannot be negative.")
    usage = get_or_create_usage(db, user_id, agent_id, source)
    if source == TeachingSource.GLOBAL_CURRICULUM and usage.paid_access:
        usage.response_chars_limit = 0
        usage.response_chars_used += characters
        db.flush()
        return None
    limit = DAILY_RESPONSE_CHAR_LIMIT
    usage.response_chars_limit = limit
    if usage.response_chars_used + characters > limit:
        raise TeachingAccessError(f"Daily response limit of {limit} characters has been reached.")
    usage.response_chars_used += characters
    db.flush()
    return max(0, limit - usage.response_chars_used)


def start_step(db: Session, *, user_id: str, agent_id: str, source: TeachingSource, scope_key: str, position: int) -> TeachingStep:
    step = db.scalar(select(TeachingStep).where(
        TeachingStep.user_id == user_id, TeachingStep.agent_id == agent_id,
        TeachingStep.source == source, TeachingStep.scope_key == scope_key,
        TeachingStep.position == position,
    ))
    if step is None:
        step = TeachingStep(
            user_id=user_id, agent_id=agent_id, source=source,
            scope_key=scope_key, position=position,
        )
        db.add(step)
        db.flush()
    return step


def record_understanding_check(db: Session, *, step_id: str, verified: bool) -> TeachingStep:
    step = db.get(TeachingStep, step_id)
    if step is None:
        raise TeachingAccessError("Teaching step not found.")
    step.attempts += 1
    step.understanding_verified = verified
    db.flush()
    return step


def confirm_student_understanding(db: Session, *, step_id: str, confirmed: bool) -> TeachingStep:
    step = db.get(TeachingStep, step_id)
    if step is None:
        raise TeachingAccessError("Teaching step not found.")
    if step.status == TeachingStepStatus.COMPLETED:
        return step
    if not confirmed:
        step.student_confirmed = False
        db.flush()
        return step
    if not step.understanding_verified:
        raise TeachingAccessError("The student cannot complete the step until the teacher verifies understanding.")
    step.student_confirmed = True
    step.status = TeachingStepStatus.COMPLETED
    step.completed_at = datetime.utcnow()
    db.flush()
    return step


def record_exam_result(
    db: Session, *, user_id: str, agent_id: str, content_file_id: str,
    score: float, max_score: float, passed: bool,
) -> TeachingAssessment:
    if max_score <= 0 or score < 0 or score > max_score:
        raise TeachingAccessError("Invalid exam score.")
    result = TeachingAssessment(
        user_id=user_id, agent_id=agent_id, content_file_id=content_file_id,
        score=score, max_score=max_score,
        percentage=(score / max_score) * 100,
        passed=passed,
    )
    db.add(result)
    db.flush()
    db.add(TeachingAssessmentReport(assessment_id=result.id, status="pending"))
    from app.agents.main_manager import MainManagerService
    MainManagerService.process_event(
        db,
        "education.exam_result",
        user_id,
        {
            "resource_type": "teaching_assessment",
            "resource_id": result.id,
            "assessment_id": result.id,
            "student_id": user_id,
            "teacher_agent_id": agent_id,
            "content_file_id": content_file_id,
            "score": score,
            "max_score": max_score,
            "percentage": result.percentage,
            "passed": passed,
        },
    )
    # The exam is free. It closes the current file's teaching cycle,
    # while the student may still use the remaining daily file slots.
    db.flush()
    return result


def grant_paid_global_access(db: Session, *, user_id: str, agent_id: str) -> TeachingUsage:
    usage = get_or_create_usage(db, user_id, agent_id, TeachingSource.GLOBAL_CURRICULUM)
    usage.paid_access = True
    usage.response_chars_limit = 0
    usage.response_chars_used = 0
    db.flush()
    return usage
