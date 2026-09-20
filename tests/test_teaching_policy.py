from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.agents.models import Agent, AgentKind, AgentStatus
from app.agents.teaching_policy import (
    TeachingAccessError,
    confirm_student_understanding,
    record_understanding_check,
    register_student_file,
    start_step,
)
from app.db.base import Base
from app.db.models import (
    ContentFile,
    Institution,
    TeachingSource,
    User,
)


def setup():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    user = User(display_name="Student", email="student@example.com")
    institution = Institution(name="TOFAN", code="TOFAN", organization_type="academy")
    db.add_all([user, institution])
    db.flush()
    agent = Agent(
        name="Teacher",
        slug="teacher-test",
        kind=AgentKind.TEACHER,
        status=AgentStatus.ACTIVE,
        teacher_institution_id=institution.id,
        system_prompt="test",
    )
    db.add(agent)
    db.flush()
    return db, user, agent


def test_student_file_limit_is_three():
    db, user, agent = setup()
    for index in range(3):
        content = ContentFile(
            original_name=f"{index}.pdf",
            storage_key=f"student/{index}.pdf",
            teaching_source=TeachingSource.STUDENT_FILES,
        )
        db.add(content)
        db.flush()
        register_student_file(
            db, user_id=user.id, agent_id=agent.id, content_file=content
        )
    try:
        content = ContentFile(
            original_name="four.pdf",
            storage_key="student/4.pdf",
            teaching_source=TeachingSource.STUDENT_FILES,
        )
        db.add(content)
        db.flush()
        register_student_file(
            db, user_id=user.id, agent_id=agent.id, content_file=content
        )
        assert False, "fourth file must be rejected"
    except TeachingAccessError:
        pass


def test_step_requires_verification_and_confirmation():
    db, user, agent = setup()
    step = start_step(
        db,
        user_id=user.id,
        agent_id=agent.id,
        source=TeachingSource.GLOBAL_CURRICULUM,
        scope_key="lesson-1",
        position=1,
    )
    try:
        confirm_student_understanding(db, step_id=step.id, confirmed=True)
        assert False, "confirmation without verification must fail"
    except TeachingAccessError:
        pass

    record_understanding_check(db, step_id=step.id, verified=True)
    confirm_student_understanding(db, step_id=step.id, confirmed=True)
    assert step.status == "completed"
    assert step.understanding_verified is True
    assert step.student_confirmed is True


def test_global_free_limit_counts_completed_steps_only():
    db, user, agent = setup()
    for position in range(1, 6):
        step = start_step(
            db,
            user_id=user.id,
            agent_id=agent.id,
            source=TeachingSource.GLOBAL_CURRICULUM,
            scope_key="lesson-1",
            position=position,
        )
        record_understanding_check(db, step_id=step.id, verified=True)
        confirm_student_understanding(db, step_id=step.id, confirmed=True)

    try:
        start_step(
            db,
            user_id=user.id,
            agent_id=agent.id,
            source=TeachingSource.GLOBAL_CURRICULUM,
            scope_key="lesson-1",
            position=6,
        )
        assert False, "sixth free global step must be rejected"
    except TeachingAccessError:
        pass
