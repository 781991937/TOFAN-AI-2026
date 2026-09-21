"""Contract tests for the native curriculum catalog and admin content API."""

import pytest
from pydantic import ValidationError

from app.api.academy_admin import (
    CurriculumCreate,
    NativeCourseCreate,
    NativeLessonCreate,
    NativeUnitCreate,
    SpecialtyCreate,
    StageCreate,
)
from app.api.content_admin import ContentStatusUpdate
from app.db.curriculum_models import (
    CurriculumCourse,
    CurriculumLesson,
    CurriculumStage,
    CurriculumUnit,
)
from app.db.models import ContentStatus


def test_curriculum_create_requires_identity_fields():
    payload = CurriculumCreate(slug="ai", name="Artificial Intelligence", version="1.0")
    assert payload.slug == "ai"
    assert payload.version == "1.0"


@pytest.mark.parametrize(
    ("factory", "kwargs"),
    [
        (SpecialtyCreate, {"name": "AI", "code": "AI"}),
        (StageCreate, {"curriculum_id": "c", "specialty_id": "s", "code": "Y1S1", "name": "Year 1 / Semester 1", "position": 1}),
        (NativeCourseCreate, {"curriculum_id": "c", "stage_id": "s", "code": "CS101", "name": "Programming", "position": 1}),
        (NativeUnitCreate, {"course_id": "c", "title": "Unit 1", "position": 1}),
        (NativeLessonCreate, {"unit_id": "u", "title": "Lesson 1", "position": 1}),
    ],
)
def test_native_create_schemas_accept_minimum_valid_payload(factory, kwargs):
    assert factory(**kwargs)


@pytest.mark.parametrize(
    ("factory", "field"),
    [
        (SpecialtyCreate, "name"),
        (SpecialtyCreate, "code"),
        (StageCreate, "code"),
        (StageCreate, "name"),
        (NativeCourseCreate, "code"),
        (NativeCourseCreate, "name"),
        (NativeUnitCreate, "title"),
        (NativeLessonCreate, "title"),
    ],
)
def test_native_create_schemas_reject_empty_required_text(factory, field):
    base = {
        "name": "x", "code": "x", "curriculum_id": "c", "specialty_id": "s",
        "stage_id": "s", "unit_id": "u", "course_id": "c", "title": "x", "position": 1,
    }
    base[field] = ""
    with pytest.raises(ValidationError):
        factory(**base)


@pytest.mark.parametrize("factory", [StageCreate, NativeCourseCreate, NativeUnitCreate, NativeLessonCreate])
def test_native_create_schemas_reject_zero_position(factory):
    if factory is StageCreate:
        kwargs = {"curriculum_id": "c", "specialty_id": "s", "code": "S", "name": "Stage", "position": 0}
    elif factory is NativeCourseCreate:
        kwargs = {"curriculum_id": "c", "stage_id": "s", "code": "C", "name": "Course", "position": 0}
    elif factory is NativeUnitCreate:
        kwargs = {"course_id": "c", "title": "Unit", "position": 0}
    else:
        kwargs = {"unit_id": "u", "title": "Lesson", "position": 0}
    with pytest.raises(ValidationError):
        factory(**kwargs)


def test_content_status_update_accepts_enum_values():
    payload = ContentStatusUpdate(status=ContentStatus.DRAFT)
    assert payload.status == ContentStatus.DRAFT


def test_curriculum_ordering_constraints_are_scoped_to_parent():
    def constraints(model):
        return {
            tuple(column.name for column in constraint.columns)
            for constraint in model.__table__.constraints
            if hasattr(constraint, "columns")
        }

    assert ("curriculum_id", "code") in constraints(CurriculumStage)
    assert ("curriculum_id", "code") in constraints(CurriculumCourse)
    assert ("course_id", "position") in constraints(CurriculumUnit)
    assert ("unit_id", "position") in constraints(CurriculumLesson)
