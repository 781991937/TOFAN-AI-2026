from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.student_onboarding import get_onboarding_state
from app.api.student_identity import get_academy_catalog
from app.db.base import Base
from app.db.identity_models import PaymentStatus, PaymentTransaction, ProfileStatus, StudentProfile, UserType
from app.db.models import AcademicPeriod, AcademicUnit, ContentFile, ContentStatus, Course, Entitlement, Institution, Lecture, TeachingAccess, TeachingSource, Unit, User


def setup_db():
    engine = create_engine("sqlite:///:memory:")
    import app.agents.models  # noqa: F401
    import app.db.assessment_models  # noqa: F401
    import app.db.assessment_question_models  # noqa: F401
    import app.db.identity_models  # noqa: F401
    Base.metadata.create_all(engine)
    return Session(engine)


def seed_user(db):
    user = User(display_name="Student", email="student@example.com")
    db.add(user)
    db.commit()
    return user


def test_onboarding_starts_at_profile():
    db = setup_db()
    user = seed_user(db)

    state = get_onboarding_state(db, user)

    assert state["step"] == "profile"
    assert state["next_action"] == "complete_profile"


def test_verified_student_is_sent_to_payment():
    db = setup_db()
    user = seed_user(db)
    db.add(
        StudentProfile(
            user_id=user.id,
            user_type=UserType.INDEPENDENT_LEARNER,
            full_name="Student",
            profile_status=ProfileStatus.VERIFIED,
            biometric_verified=True,
        )
    )
    db.commit()

    state = get_onboarding_state(db, user)

    assert state["step"] == "payment"
    assert state["next_action"] == "request_global_curriculum"


def test_pending_payment_waits_for_owner_approval():
    db = setup_db()
    user = seed_user(db)
    db.add(
        StudentProfile(
            user_id=user.id,
            user_type=UserType.INDEPENDENT_LEARNER,
            full_name="Student",
            profile_status=ProfileStatus.VERIFIED,
            biometric_verified=True,
        )
    )
    db.flush()
    db.add(
        PaymentTransaction(
            user_id=user.id,
            product_key="global_curriculum",
            status=PaymentStatus.PENDING,
        )
    )
    db.commit()

    state = get_onboarding_state(db, user)

    assert state["step"] == "owner_approval"
    assert state["next_action"] == "wait_for_owner_confirmation"


def test_entitled_student_can_open_global_curriculum():
    db = setup_db()
    user = seed_user(db)
    db.add(
        StudentProfile(
            user_id=user.id,
            user_type=UserType.INDEPENDENT_LEARNER,
            full_name="Student",
            profile_status=ProfileStatus.VERIFIED,
            biometric_verified=True,
        )
    )
    db.flush()
    db.add(
        Entitlement(
            user_id=user.id,
            access_type=TeachingAccess.PAID.value,
        )
    )
    db.commit()

    state = get_onboarding_state(db, user)

    assert state["step"] == "curriculum"
    assert state["completed"] is True
    assert state["next_action"] == "open_global_curriculum"

def test_verified_university_student_gets_academy_catalog_with_free_first_term():
    db = setup_db()
    user = seed_user(db)
    institution = Institution(name="University", code="U1")
    db.add(institution)
    db.flush()
    college = AcademicUnit(institution_id=institution.id, name="College", unit_type="college")
    db.add(college)
    db.flush()
    major = AcademicUnit(institution_id=institution.id, parent_id=college.id, name="AI", unit_type="major")
    db.add(major)
    db.flush()
    period = AcademicPeriod(institution_id=institution.id, name="Year 1 Term 1", kind="semester", year_number=1, term_number=1)
    db.add(period)
    db.flush()
    course = Course(academic_unit_id=major.id, academic_period_id=period.id, name="Introduction to AI")
    db.add(course)
    db.flush()
    unit = Unit(course_id=course.id, title="Unit 1", position=1)
    db.add(unit)
    db.flush()
    lecture = Lecture(unit_id=unit.id, title="Lecture 1", position=1, status=ContentStatus.FREE)
    db.add(lecture)
    db.flush()
    content = ContentFile(
        lecture_id=lecture.id,
        teaching_source=TeachingSource.GLOBAL_CURRICULUM,
        original_name="lecture.pdf",
        storage_key="academy/lecture.pdf",
        extracted_text="AI content",
        status=ContentStatus.FREE,
    )
    db.add(content)
    db.add(StudentProfile(
        user_id=user.id, user_type=UserType.UNIVERSITY_STUDENT, full_name="Student",
        institution_id=institution.id, college_unit_id=college.id, major_unit_id=major.id,
        profile_status=ProfileStatus.VERIFIED, biometric_verified=True,
    ))
    db.commit()

    state = get_academy_catalog(db, user)

    assert state["scope"] == "academy"
    assert state["courses"][0]["access_tier"] == "free"
    assert state["courses"][0]["lectures"][0]["files"][0]["accessible"] is True