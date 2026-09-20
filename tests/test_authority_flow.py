"""Integration checks for the TOFAN authority and native curriculum flow."""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.agents.main_manager import MainManagerService
from app.agents.models import Agent, AgentKind, AgentStatus
from app.agents.payment_tools import confirm_payment_transaction
from app.agents.teacher import create_curriculum_teacher_agent
from app.db.base import Base
from app.db.curriculum_models import Curriculum, CurriculumCourse, CurriculumStage, Specialty
from app.db.identity_models import PaymentStatus, PaymentTransaction, StudentProfile, UserType
from app.db.models import Entitlement, User, TeachingAccess


def setup_db():
    engine = create_engine("sqlite:///:memory:")
    import app.agents.models  # noqa: F401
    import app.db.assessment_models  # noqa: F401
    import app.db.assessment_question_models  # noqa: F401
    import app.db.identity_models  # noqa: F401
    Base.metadata.create_all(engine)
    return Session(engine)


def seed_authority(db):
    manager = Agent(
        name="Main Manager",
        slug="tofan-main",
        kind=AgentKind.ORCHESTRATOR,
        status=AgentStatus.ACTIVE,
        system_prompt="manager",
    )
    db.add(manager)
    db.flush()
    return manager


def test_payment_confirmation_grants_global_access_and_is_idempotent():
    db = setup_db()
    manager = seed_authority(db)
    user = User(display_name="Student", email="student@example.com")
    db.add(user)
    db.flush()
    profile = StudentProfile(
        user_id=user.id,
        user_type=UserType.INDEPENDENT_LEARNER,
        full_name="Student",
    )
    db.add(profile)
    db.flush()

    payment = PaymentTransaction(
        user_id=user.id,
        product_key="global_curriculum",
        status=PaymentStatus.PENDING,
        amount=100,
        currency="USD",
        reference="TEST-001",
    )
    db.add(payment)
    db.commit()

    first = confirm_payment_transaction(db, payment.id)
    db.commit()
    assert first["global_access"] == "active"
    assert first["user_id"] == user.id
    assert payment.status == PaymentStatus.CONFIRMED
    assert payment.confirmed_by_agent_id == manager.id

    entitlements = db.scalars(
        select(Entitlement).where(
            Entitlement.user_id == user.id,
            Entitlement.access_type == TeachingAccess.PAID.value,
            Entitlement.content_file_id.is_(None),
        )
    ).all()
    assert len(entitlements) == 1

    second = confirm_payment_transaction(db, payment.id)
    assert second["idempotent"] is True
    assert db.scalar(
        select(Entitlement).where(
            Entitlement.user_id == user.id,
            Entitlement.access_type == TeachingAccess.PAID.value,
            Entitlement.content_file_id.is_(None),
        )
    ) is not None


def test_main_manager_requires_active_orchestrator():
    db = setup_db()
    try:
        MainManagerService.get_manager(db)
    except RuntimeError as exc:
        assert "not active" in str(exc)
    else:
        raise AssertionError("inactive/missing main manager must be rejected")


def test_native_teacher_is_bound_to_tofan_course():
    db = setup_db()
    seed_authority(db)

    specialty = Specialty(name="Artificial Intelligence", code="AI")
    curriculum = Curriculum(
        slug="tofan-ai-test",
        name="TOFAN AI Test Curriculum",
        version="1",
        status="active",
    )
    db.add_all([specialty, curriculum])
    db.flush()

    stage = CurriculumStage(
        curriculum_id=curriculum.id,
        specialty_id=specialty.id,
        code="F1",
        name="Programming",
        position=1,
    )
    db.add(stage)
    db.flush()

    course = CurriculumCourse(
        curriculum_id=curriculum.id,
        stage_id=stage.id,
        code="AI-PRG-101",
        name="Python Fundamentals",
        position=1,
        is_active=True,
    )
    db.add(course)
    db.flush()

    teacher = create_curriculum_teacher_agent(
        db,
        name="Python Teacher",
        slug="teacher-tofan-ai-prg-101-test",
        curriculum_course_id=course.id,
    )
    db.commit()

    assert teacher.kind == AgentKind.TEACHER
    assert teacher.curriculum_course_id == course.id
    assert teacher.teacher_course_id is None


def test_payment_confirmation_rejects_inactive_main_manager():
    db = setup_db()
    manager = Agent(
        name="Main Manager",
        slug="tofan-main",
        kind=AgentKind.ORCHESTRATOR,
        status=AgentStatus.PAUSED,
        system_prompt="manager",
    )
    user = User(display_name="Student", email="paused@example.com")
    db.add_all([manager, user])
    db.flush()
    payment = PaymentTransaction(
        user_id=user.id,
        product_key="global_curriculum",
        status=PaymentStatus.PENDING,
        amount=100,
        currency="USD",
    )
    db.add(payment)
    db.commit()

    try:
        confirm_payment_transaction(db, payment.id)
    except ValueError as exc:
        assert "not configured" in str(exc) or "active" in str(exc)
    else:
        raise AssertionError("inactive main manager must not confirm payments")
