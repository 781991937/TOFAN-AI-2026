from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.agents.academy_access_policy import content_access_tier, period_access_tier, validate_content_status
from app.db.base import Base
from app.db.models import (
    AcademyAccessTier,
    AcademicPeriod,
    AcademicUnit,
    ContentFile,
    ContentStatus,
    Course,
    Institution,
    Lecture,
    Unit,
    TeachingSource,
)


def setup():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def make_content(db: Session, *, year: int, term: int) -> ContentFile:
    institution = Institution(name=f"University {year}-{term}", code=f"U-{year}-{term}")
    unit = AcademicUnit(
        institution=institution,
        name="AI",
        unit_type="specialty",
    )
    period = AcademicPeriod(
        institution=institution,
        name=f"Term {year}-{term}",
        kind="semester",
        year_number=year,
        term_number=term,
    )
    course = Course(
        academic_unit=unit,
        academic_period_id=period.id,
        name="AI Course",
    )
    db.add_all([institution, unit, period, course])
    db.flush()

    course_unit = Unit(course_id=course.id, title="Unit 1", position=1)
    db.add(course_unit)
    db.flush()
    lecture = Lecture(unit_id=course_unit.id, title="Lecture 1", position=1)
    db.add(lecture)
    db.flush()

    content = ContentFile(
        lecture_id=lecture.id,
        original_name="lesson.txt",
        storage_key=f"academy/{year}-{term}.txt",
        teaching_source=TeachingSource.GLOBAL_CURRICULUM,
        status=ContentStatus.DRAFT,
        extracted_text="lesson",
    )
    db.add(content)
    db.flush()
    return content


def test_first_semester_of_first_year_is_free():
    db = setup()
    content = make_content(db, year=1, term=1)

    assert content_access_tier(db, content.id) == AcademyAccessTier.FREE
    validate_content_status(db, content_file=content, requested_status=ContentStatus.FREE.value)


def test_later_semesters_are_paid():
    db = setup()
    first_year_second_term = make_content(db, year=1, term=2)
    second_year_first_term = make_content(db, year=2, term=1)

    assert content_access_tier(db, first_year_second_term.id) == AcademyAccessTier.PAID
    assert content_access_tier(db, second_year_first_term.id) == AcademyAccessTier.PAID

    validate_content_status(
        db,
        content_file=first_year_second_term,
        requested_status=ContentStatus.PAID.value,
    )


def test_draft_content_is_not_publicly_free_or_paid():
    db = setup()
    content = make_content(db, year=1, term=1)

    validate_content_status(
        db,
        content_file=content,
        requested_status=ContentStatus.DRAFT.value,
    )
    assert content.status == ContentStatus.DRAFT


def test_free_first_semester_cannot_be_published_as_paid():
    db = setup()
    content = make_content(db, year=1, term=1)

    try:
        validate_content_status(
            db,
            content_file=content,
            requested_status=ContentStatus.PAID.value,
        )
    except ValueError as exc:
        assert "free" in str(exc)
    else:
        raise AssertionError("First-semester content must not be published as paid.")


def test_student_private_content_is_not_affected_by_academy_tier_rule():
    db = setup()
    content = make_content(db, year=1, term=1)
    content.teaching_source = TeachingSource.STUDENT_FILES
    content.status = ContentStatus.PRIVATE

    try:
        validate_content_status(
            db,
            content_file=content,
            requested_status=ContentStatus.FREE.value,
        )
    except ValueError as exc:
        assert "academy curriculum" in str(exc)
    else:
        raise AssertionError("Student files must remain private and outside academy publishing rules.")
