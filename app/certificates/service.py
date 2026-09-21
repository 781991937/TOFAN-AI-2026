"""Certificate issuance service driven by verified course completion."""

from datetime import datetime
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.curriculum_models import CourseAssessment, CurriculumCourse
from app.db.assessment_models import CurriculumAssessmentAttempt
from app.db.models import TeachingStep, TeachingStepStatus, TeachingSource
from app.db.certificate_models import Certificate


def issue_course_certificate(db: Session, user_id: str, course_id: str) -> Certificate | None:
    course = db.get(CurriculumCourse, course_id)
    if course is None:
        return None
    steps = db.scalars(select(TeachingStep).where(
        TeachingStep.user_id == user_id,
        TeachingStep.source == TeachingSource.GLOBAL_CURRICULUM,
    )).all()
    course_steps = [s for s in steps if f"course:{course_id}:" in (s.scope_key or "")]
    if not course_steps or not all(s.status == TeachingStepStatus.COMPLETED for s in course_steps):
        return None
    assessment = db.scalar(select(CourseAssessment).where(
        CourseAssessment.course_id == course_id,
        CourseAssessment.assessment_type == "course",
    ))
    if assessment is not None:
        passed_attempt = db.scalar(select(CurriculumAssessmentAttempt).where(
            CurriculumAssessmentAttempt.user_id == user_id,
            CurriculumAssessmentAttempt.assessment_id == assessment.id,
            CurriculumAssessmentAttempt.passed.is_(True),
        ).order_by(CurriculumAssessmentAttempt.submitted_at.desc()))
        if passed_attempt is None:
            return None

    existing = db.scalar(select(Certificate).where(
        Certificate.user_id == user_id, Certificate.course_id == course_id
    ))
    if existing:
        return existing
    certificate = Certificate(
        certificate_number=f"TOFAN-{datetime.utcnow():%Y%m%d}-{uuid4().hex[:10].upper()}",
        user_id=user_id, course_id=course_id,
        title=f"شهادة إتمام مقرر {course.name}", status="issued",
        metadata_json='{"verified_by":"tofan-main"}',
    )
    db.add(certificate)
    db.flush()
    return certificate


def list_certificates(db: Session, user_id: str) -> list[Certificate]:
    return db.scalars(select(Certificate).where(
        Certificate.user_id == user_id
    ).order_by(Certificate.issued_at.desc())).all()
