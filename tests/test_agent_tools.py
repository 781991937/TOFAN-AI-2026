"""Tests for the Main Agent academy tools."""

import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.tools import build_default_registry
from app.db.base import Base
from app.db.models import AcademicUnit, Course, Institution, Lecture, Unit


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def seed_academy(db):
    institution = Institution(name="جامعة صنعاء", code="SU")
    db.add(institution)
    db.flush()

    unit = AcademicUnit(
        institution_id=institution.id,
        name="مركز الحاسب الآلي",
        unit_type="center",
    )
    db.add(unit)
    db.flush()

    course = Course(
        academic_unit_id=unit.id,
        name="مقدمة الذكاء الاصطناعي",
        code="AI101",
    )
    db.add(course)
    db.flush()

    course_unit = Unit(course_id=course.id, title="الوكلاء الأذكياء", position=1)
    db.add(course_unit)
    db.flush()

    lecture = Lecture(
        unit_id=course_unit.id,
        title="الوكيل العقلاني",
        position=1,
    )
    db.add(lecture)
    db.commit()


def test_academy_structure_and_search():
    db = make_db()
    seed_academy(db)
    registry = build_default_registry()

    structure = json.loads(registry.get("academy.structure").handler(db, ""))
    assert structure["institutions"][0]["institution"]["name"] == "جامعة صنعاء"

    result = json.loads(
        registry.get("academy.search").handler(
            db, json.dumps({"query": "ذكاء اصطناعي", "limit": 10}, ensure_ascii=False)
        )
    )
    assert result["courses"][0]["code"] == "AI101"


def test_search_rejects_invalid_json():
    db = make_db()
    registry = build_default_registry()

    try:
        registry.get("academy.search").handler(db, "not-json")
    except RuntimeError:
        pass
    else:
        raise AssertionError("Expected invalid JSON to fail")
