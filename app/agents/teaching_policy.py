"""Teaching access and mastery rules for TOFAN teacher agents.

The limits are product policy, not prompt instructions:
- Student-file teaching: 3 uploaded files per student/teacher.
- Global curriculum teaching: 5 completed free steps before paid access.
- A step is completed only when the teacher has verified understanding and the
  student has explicitly confirmed understanding.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Agent,
    ContentFile,
    TeachingSource,
    TeachingStep,
    TeachingStepStatus,
    TeachingUsage,
)


class TeachingAccessError(ValueError):
    pass


STUDENT_FILE_LIMIT = 3
GLOBAL_FREE_STEP_LIMIT = 5


def get_or_create_usage(db: Session, user_id: str, agent_id: str, source: TeachingSource) -> TeachingUsage:
    usage = db.scalar(
        select(TeachingUsage).where(
            TeachingUsage.user_id == user_id,
            TeachingUsage.agent_id == agent_id,
            TeachingUsage.source == source,
        )
    )
    if usage is None:
        usage = TeachingUsage(
            user_id=user_id,
            agent_id=agent_id,
            source=source,
            files_limit=STUDENT_FILE_LIMIT,
            free_steps_limit=GLOBAL_FREE_STEP_LIMIT,
        )
        db.add(usage)
        db.flush()
    return usage


def register_student_file(
    db: Session,
    *,
    user_id: str,
    agent_id: str,
    content_file: ContentFile,
) -> TeachingUsage:
    """Reserve one of the three free student-file slots."""
    usage = get_or_create_usage(db, user_id, agent_id, TeachingSource.STUDENT_FILES)
    if usage.files_used >= usage.files_limit:
        raise TeachingAccessError("The free student-file limit of 3 files has been reached.")
    usage.files_used += 1
    content_file.uploaded_by_user_id = user_id
    content_file.teaching_source = TeachingSource.STUDENT_FILES
    db.flush()
    return usage


def global_free_access_remaining(
    db: Session, *, user_id: str, agent_id: str
) -> int:
    usage = get_or_create_usage(db, user_id, agent_id, TeachingSource.GLOBAL_CURRICULUM)
    if usage.paid_access:
        return 0
    return max(0, usage.free_steps_limit - usage.free_steps_used)


def start_step(
    db: Session,
    *,
    user_id: str,
    agent_id: str,
    source: TeachingSource,
    scope_key: str,
    position: int,
) -> TeachingStep:
    usage = get_or_create_usage(db, user_id, agent_id, source)
    if source == TeachingSource.GLOBAL_CURRICULUM and not usage.paid_access:
        if usage.free_steps_used >= usage.free_steps_limit:
            raise TeachingAccessError(
                "The free global curriculum limit of 5 completed steps has been reached."
            )

    step = db.scalar(
        select(TeachingStep).where(
            TeachingStep.user_id == user_id,
            TeachingStep.agent_id == agent_id,
            TeachingStep.source == source,
            TeachingStep.scope_key == scope_key,
            TeachingStep.position == position,
        )
    )
    if step is None:
        step = TeachingStep(
            user_id=user_id,
            agent_id=agent_id,
            source=source,
            scope_key=scope_key,
            position=position,
        )
        db.add(step)
        db.flush()
    return step


def record_understanding_check(
    db: Session,
    *,
    step_id: str,
    verified: bool,
) -> TeachingStep:
    step = db.get(TeachingStep, step_id)
    if step is None:
        raise TeachingAccessError("Teaching step not found.")
    step.attempts += 1
    step.understanding_verified = verified
    db.flush()
    return step


def confirm_student_understanding(
    db: Session,
    *,
    step_id: str,
    confirmed: bool,
) -> TeachingStep:
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
        raise TeachingAccessError(
            "The student cannot complete the step until the teacher verifies understanding."
        )
    step.student_confirmed = True
    step.status = TeachingStepStatus.COMPLETED
    from datetime import datetime
    step.completed_at = datetime.utcnow()

    if step.source == TeachingSource.GLOBAL_CURRICULUM:
        usage = get_or_create_usage(
            db, step.user_id, step.agent_id, TeachingSource.GLOBAL_CURRICULUM
        )
        if not usage.paid_access:
            usage.free_steps_used += 1
    db.flush()
    return step


def grant_paid_global_access(db: Session, *, user_id: str, agent_id: str) -> TeachingUsage:
    usage = get_or_create_usage(db, user_id, agent_id, TeachingSource.GLOBAL_CURRICULUM)
    usage.paid_access = True
    db.flush()
    return usage
