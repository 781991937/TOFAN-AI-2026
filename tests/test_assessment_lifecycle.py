import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.models import Agent, AgentKind, AgentRole, AgentStatus
from app.api.student_assessments import SubmitRequest, start_assessment, submit_assessment
from app.auth.authentication import register_email
from app.db.assessment_models import AssessmentAttemptStatus, CurriculumAssessmentAttempt
from app.db.assessment_question_models import CurriculumAssessmentQuestion
from app.db.base import Base
from app.db.curriculum_models import Curriculum, CurriculumCourse, CurriculumStage
from app.db.curriculum_models import CourseAssessment, Specialty

# Import model modules so all tables are registered with the declarative base.
import app.agents.memory  # noqa: F401
import app.db.models  # noqa: F401
import app.db.progress_models  # noqa: F401


def test_assessment_records_start_submit_and_grade_lifecycle():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    student = register_email(db, "student@example.com", "correct horse battery", "Student")
    specialty = Specialty(code="AI", name="Artificial Intelligence")
    curriculum = Curriculum(
        slug="tofan-ai-v1", name="TOFAN AI", version="1.0", status="active"
    )
    db.add_all([specialty, curriculum])
    db.flush()
    stage = CurriculumStage(
        curriculum_id=curriculum.id,
        specialty_id=specialty.id,
        code="Y1S1",
        name="Year 1 Semester 1",
        position=1,
    )
    db.add(stage)
    db.flush()
    course = CurriculumCourse(
        curriculum_id=curriculum.id,
        stage_id=stage.id,
        code="AI-FND-001",
        name="Computer Skills",
        position=1,
    )
    db.add(course)
    db.flush()
    assessment = CourseAssessment(
        course_id=course.id,
        assessment_type="course",
        title="Final assessment",
        pass_percentage=60,
    )
    teacher = Agent(
        name="AI Teacher",
        slug="ai-teacher",
        kind=AgentKind.TEACHER,
        role=AgentRole.TEACHER,
        status=AgentStatus.ACTIVE,
        curriculum_course_id=course.id,
    )
    manager = Agent(
        name="TOFAN Main Agent",
        slug="tofan-main",
        kind=AgentKind.ORCHESTRATOR,
        role=AgentRole.GENERAL_MANAGER,
        status=AgentStatus.ACTIVE,
    )
    db.add_all([assessment, teacher, manager])
    db.flush()
    db.add(
        CurriculumAssessmentQuestion(
            assessment_id=assessment.id,
            position=1,
            question_type="mcq",
            prompt="What is 2 + 2?",
            options_json=json.dumps(["3", "4", "5", "6"]),
            correct_answer="4",
            explanation="Basic arithmetic.",
            points=1,
        )
    )
    db.commit()

    started = start_assessment(assessment.id, db, student)
    assert started["status"] == AssessmentAttemptStatus.IN_PROGRESS
    assert started["attempt_id"]

    result = submit_assessment(
        assessment.id,
        SubmitRequest(attempt_id=started["attempt_id"], answers={"1": "4"}),
        db,
        student,
    )

    attempt = db.get(CurriculumAssessmentAttempt, started["attempt_id"])
    assert result["passed"] is True
    assert attempt.status == AssessmentAttemptStatus.GRADED
    assert attempt.started_at is not None
    assert attempt.submitted_at is not None
    assert attempt.graded_at is not None