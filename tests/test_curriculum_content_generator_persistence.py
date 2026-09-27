import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.curriculum_content_generator import generate_next_courses
from app.db.base import Base
from app.db.curriculum_models import Curriculum, CurriculumCourse, CurriculumStage, CurriculumUnit, CurriculumLesson, LearningOutcome, Specialty


class FakeProvider:
    provider_name = "test"
    model_name = "test"

    def generate(self, messages, *, system_prompt=None, tools=None):
        long_text = "# Lesson\n\n" + ("Academic explanation, example, application, and verification exercise. " * 10)
        return type("Response", (), {"content": json.dumps({
            "learning_outcomes": ["Understand the topic.", "Apply the topic."],
            "units": [
                {"position": 1, "title": "Unit 1", "lessons": [{"position": 1, "title": "Lesson 1", "description": "Intro", "learning_objectives": ["Understand.", "Apply."], "content_markdown": long_text}]},
                {"position": 2, "title": "Unit 2", "lessons": [{"position": 1, "title": "Lesson 2", "description": "Practice", "learning_objectives": ["Analyze.", "Apply."], "content_markdown": long_text}]},
                {"position": 3, "title": "Unit 3", "lessons": [{"position": 1, "title": "Lesson 3", "description": "Integration", "learning_objectives": ["Design.", "Evaluate."], "content_markdown": long_text}]},
            ]
        }, ensure_ascii=False)})


def test_generate_validate_save_persists_one_course():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    specialty = Specialty(code="AI", name="Artificial Intelligence")
    db.add(specialty)
    db.flush()
    curriculum = Curriculum(slug="tofan-ai-v1", name="TOFAN AI", version="1.0", status="active")
    db.add(curriculum)
    db.flush()
    stage = CurriculumStage(curriculum_id=curriculum.id, specialty_id=specialty.id, code="Y1S1", name="Year 1 Semester 1", position=1)
    db.add(stage)
    db.flush()
    db.add(CurriculumCourse(curriculum_id=curriculum.id, stage_id=stage.id, code="AI-FND-001", name="Computer Skills", position=1))
    db.commit()

    result = generate_next_courses(db, specialty_id="AI", max_courses=1, provider=FakeProvider())

    assert result["processed"] == 1
    assert db.query(CurriculumUnit).count() == 3
    assert db.query(CurriculumLesson).count() == 3
    assert db.query(LearningOutcome).count() == 2
    assert all(x.content_markdown for x in db.query(CurriculumLesson).all())
