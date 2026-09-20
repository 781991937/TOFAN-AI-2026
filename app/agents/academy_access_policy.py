"""Access policy for academy content linked to the dynamic academic hierarchy.

The first semester of the first academic year is free for every specialty.
All other academic periods are paid. The rule is based on explicit numeric
period metadata, not on names or a fixed number of periods.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AcademyAccessTier,
    AcademicPeriod,
    ContentFile,
    Course,
    Lecture,
    Unit,
)


def period_access_tier(period: AcademicPeriod | None) -> AcademyAccessTier:
    if period is not None and period.year_number == 1 and period.term_number == 1:
        return AcademyAccessTier.FREE
    return AcademyAccessTier.PAID


def course_access_tier(db: Session, course_id: str) -> AcademyAccessTier:
    course = db.get(Course, course_id)
    if course is None:
        raise ValueError("Course not found.")
    period = db.get(AcademicPeriod, course.academic_period_id) if course.academic_period_id else None
    return period_access_tier(period)


def content_access_tier(db: Session, content_file_id: str) -> AcademyAccessTier:
    row = db.get(ContentFile, content_file_id)
    if row is None or row.lecture_id is None:
        raise ValueError("Academy content file not found.")

    lecture = db.get(Lecture, row.lecture_id)
    if lecture is None:
        raise ValueError("Lecture not found.")
    unit = db.get(Unit, lecture.unit_id)
    if unit is None:
        raise ValueError("Course unit not found.")
    return course_access_tier(db, unit.course_id)


def validate_content_status(
    db: Session,
    *,
    content_file: ContentFile,
    requested_status: str,
) -> None:
    if requested_status == "draft":
        return

    if content_file.teaching_source != "global_curriculum" or content_file.lecture_id is None:
        raise ValueError("Only academy curriculum content can be published.")

    expected = content_access_tier(db, content_file.id).value
    if requested_status != expected:
        raise ValueError(
            f"Academy content for this academic period must be published as '{expected}'."
        )
