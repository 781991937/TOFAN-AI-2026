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
    manager = Agent(
        name="Main Manager",
        slug="tofan-main",
        kind=AgentKind.ORCHESTRATOR,
        status=AgentStatus.ACTIVE,
        system_prompt="manager test",
    )
    agent = Agent(
        name="Teacher",
        slug="teacher-test",
        kind=AgentKind.TEACHER,
        status=AgentStatus.ACTIVE,
        teacher_institution_id=institution.id,
        system_prompt="test",
    )
    db.add_all([manager, agent])
    db.flush()
    return db, user, agent


def test_student_file_limit_is_three():
    db, user, agent = setup()
    for index in range(3):
        content = ContentFile(
            original_name=f"{index}.pdf",
            storage_key=f"student/{index}.pdf",
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


def test_daily_response_limit_is_2000_characters():
    db, user, agent = setup()
    from app.agents.teaching_policy import consume_response_chars, remaining_response_chars
    assert remaining_response_chars(
        db, user_id=user.id, agent_id=agent.id,
        source=TeachingSource.GLOBAL_CURRICULUM
    ) == 2000
    consume_response_chars(
        db, user_id=user.id, agent_id=agent.id,
        source=TeachingSource.GLOBAL_CURRICULUM,
        characters=2000,
    )
    assert remaining_response_chars(
        db, user_id=user.id, agent_id=agent.id,
        source=TeachingSource.GLOBAL_CURRICULUM
    ) == 0
    try:
        consume_response_chars(
            db, user_id=user.id, agent_id=agent.id,
            source=TeachingSource.GLOBAL_CURRICULUM,
            characters=1,
        )
        assert False, "response 2001 must be rejected"
    except TeachingAccessError:
        pass


def test_exam_result_is_recorded_and_reported():
    db, user, agent = setup()
    from app.agents.teaching_policy import record_exam_result
    from app.db.models import TeachingAssessmentReport
    content = ContentFile(
        original_name="lesson.pdf",
        storage_key="student/lesson.pdf",
    )
    db.add(content)
    db.flush()
    result = record_exam_result(
        db, user_id=user.id, agent_id=agent.id, content_file_id=content.id,
        score=8, max_score=10, passed=True,
    )
    report = db.query(TeachingAssessmentReport).filter(
        TeachingAssessmentReport.assessment_id == result.id
    ).one()
    assert result.percentage == 80
    assert result.passed is True
    assert report.status == "pending"


def test_student_file_metadata_is_bound_to_user_and_teacher():
    db, user, agent = setup()
    content = ContentFile(
        original_name="lesson.txt",
        storage_key="student/lesson.txt",
        uploaded_by_user_id=user.id,
        teaching_agent_id=agent.id,
        teaching_source=TeachingSource.STUDENT_FILES,
        extracted_text="Python variables are named references to values.",
        size_bytes=45,
        page_count=1,
    )
    db.add(content)
    db.flush()
    register_student_file(db, user_id=user.id, agent_id=agent.id, content_file=content)
    assert content.uploaded_by_user_id == user.id
    assert content.teaching_agent_id == agent.id
    assert content.teaching_source == TeachingSource.STUDENT_FILES
    assert content.extracted_text.startswith("Python variables")

def test_confirmed_global_access_has_no_response_quota():
    db, user, agent = setup()
    from app.agents.teaching_policy import grant_paid_global_access, consume_response_chars, remaining_response_chars
    grant_paid_global_access(db, user_id=user.id, agent_id=agent.id)
    assert remaining_response_chars(db, user_id=user.id, agent_id=agent.id, source=TeachingSource.GLOBAL_CURRICULUM) is None
    consume_response_chars(db, user_id=user.id, agent_id=agent.id, source=TeachingSource.GLOBAL_CURRICULUM, characters=100000)
    assert remaining_response_chars(db, user_id=user.id, agent_id=agent.id, source=TeachingSource.GLOBAL_CURRICULUM) is None
