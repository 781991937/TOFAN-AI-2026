from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.student_onboarding import get_onboarding_state
from app.db.base import Base
from app.db.identity_models import PaymentStatus, PaymentTransaction, ProfileStatus, StudentProfile, UserType
from app.db.models import Entitlement, TeachingAccess, User


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
