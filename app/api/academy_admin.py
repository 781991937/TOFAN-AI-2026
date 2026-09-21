"""Owner/admin academy structure management API."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.authorization import require_owner_or_admin
from app.auth.dependencies import get_db
from app.db.models import AcademicPeriod, AcademicUnit, Course, Institution, Lecture, Unit

router = APIRouter(prefix="/admin/academy", tags=["admin-academy"])


class InstitutionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code: str | None = Field(default=None, max_length=100)
    description: str | None = None
    organization_type: str = Field(default="university", max_length=30)


class AcademicUnitCreate(BaseModel):
    institution_id: str
    parent_id: str | None = None
    name: str = Field(min_length=1, max_length=255)
    unit_type: str = Field(min_length=1, max_length=50)
    description: str | None = None


class PeriodCreate(BaseModel):
    institution_id: str
    parent_id: str | None = None
    name: str = Field(min_length=1, max_length=100)
    kind: str = Field(min_length=1, max_length=30)
    year_number: int | None = Field(default=None, ge=1)
    term_number: int | None = Field(default=None, ge=1)


class CourseCreate(BaseModel):
    academic_unit_id: str
    academic_period_id: str | None = None
    name: str = Field(min_length=1, max_length=255)
    code: str | None = Field(default=None, max_length=100)
    description: str | None = None
    course_type: str = Field(default="required", max_length=30)
    credit_hours: int | None = Field(default=None, ge=0)
    theory_hours: int | None = Field(default=None, ge=0)
    practical_hours: int | None = Field(default=None, ge=0)
    prerequisites: str | None = None
    learning_stage: str = Field(default="foundation", max_length=30)


class UnitCreate(BaseModel):
    course_id: str
    title: str = Field(min_length=1, max_length=255)
    position: int = Field(ge=1)


class LectureCreate(BaseModel):
    unit_id: str
    title: str = Field(min_length=1, max_length=255)
    position: int = Field(ge=1)


@router.get("/institutions")
def list_institutions(
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    return db.scalars(select(Institution).order_by(Institution.name)).all()


@router.post("/institutions", status_code=201)
def create_institution(
    payload: InstitutionCreate,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    if payload.code and db.scalar(select(Institution).where(Institution.code == payload.code)):
        raise HTTPException(status_code=409, detail="Institution code already exists.")
    item = Institution(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/units")
def list_units(
    institution_id: str,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    return db.scalars(
        select(AcademicUnit)
        .where(AcademicUnit.institution_id == institution_id)
        .order_by(AcademicUnit.name)
    ).all()


@router.post("/units", status_code=201)
def create_unit(
    payload: AcademicUnitCreate,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    if db.get(Institution, payload.institution_id) is None:
        raise HTTPException(status_code=404, detail="Institution not found.")
    if payload.parent_id:
        parent = db.get(AcademicUnit, payload.parent_id)
        if parent is None or parent.institution_id != payload.institution_id:
            raise HTTPException(status_code=400, detail="Invalid parent unit.")
    item = AcademicUnit(**payload.model_dump())
    db.add(item)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Academic unit already exists or is invalid.")
    db.refresh(item)
    return item


@router.get("/periods")
def list_periods(
    institution_id: str,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    return db.scalars(
        select(AcademicPeriod)
        .where(AcademicPeriod.institution_id == institution_id)
        .order_by(AcademicPeriod.name)
    ).all()


@router.post("/periods", status_code=201)
def create_period(
    payload: PeriodCreate,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    if db.get(Institution, payload.institution_id) is None:
        raise HTTPException(status_code=404, detail="Institution not found.")
    if payload.parent_id:
        parent = db.get(AcademicPeriod, payload.parent_id)
        if parent is None or parent.institution_id != payload.institution_id:
            raise HTTPException(status_code=400, detail="Invalid parent academic period.")
    item = AcademicPeriod(**payload.model_dump())
    db.add(item)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Academic period already exists.")
    db.refresh(item)
    return item


@router.get("/courses")
def list_courses(
    academic_unit_id: str,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    return db.scalars(
        select(Course)
        .where(Course.academic_unit_id == academic_unit_id)
        .order_by(Course.name)
    ).all()


@router.post("/courses", status_code=201)
def create_course(
    payload: CourseCreate,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    if db.get(AcademicUnit, payload.academic_unit_id) is None:
        raise HTTPException(status_code=404, detail="Academic unit not found.")
    if payload.academic_period_id:
        period = db.get(AcademicPeriod, payload.academic_period_id)
        if period is None or period.institution_id != db.get(AcademicUnit, payload.academic_unit_id).institution_id:
            raise HTTPException(status_code=400, detail="Invalid academic period for this institution.")
    item = Course(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/units/{course_id}")
def list_course_units(
    course_id: str,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    return db.scalars(
        select(Unit).where(Unit.course_id == course_id).order_by(Unit.position)
    ).all()


@router.post("/units/{course_id}", status_code=201)
def create_course_unit(
    course_id: str,
    payload: UnitCreate,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    if payload.course_id != course_id:
        raise HTTPException(status_code=400, detail="course_id mismatch.")
    if db.get(Course, course_id) is None:
        raise HTTPException(status_code=404, detail="Course not found.")
    item = Unit(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/lectures/{unit_id}")
def list_lectures(
    unit_id: str,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    return db.scalars(
        select(Lecture).where(Lecture.unit_id == unit_id).order_by(Lecture.position)
    ).all()


@router.post("/lectures/{unit_id}", status_code=201)
def create_lecture(
    unit_id: str,
    payload: LectureCreate,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    if payload.unit_id != unit_id:
        raise HTTPException(status_code=400, detail="unit_id mismatch.")
    if db.get(Unit, unit_id) is None:
        raise HTTPException(status_code=404, detail="Course unit not found.")
    item = Lecture(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/curriculum")
def get_curriculum(
    academic_unit_id: str,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    """Return the learning tree without requiring university years/semesters.

    Academic periods are optional reference metadata. Native TOFAN learning is
    organized primarily by learning_stage (foundation/level/track/project/elective).
    """
    unit = db.get(AcademicUnit, academic_unit_id)
    if unit is None:
        raise HTTPException(status_code=404, detail="Academic unit not found.")

    periods = db.scalars(
        select(AcademicPeriod)
        .where(
            AcademicPeriod.institution_id == unit.institution_id,
            AcademicPeriod.is_active.is_(True),
        )
        .order_by(AcademicPeriod.name)
    ).all()

    period_ids = {period.id for period in periods}
    courses = db.scalars(
        select(Course)
        .where(
            Course.academic_unit_id == academic_unit_id,
            Course.is_active.is_(True),
        )
        .order_by(Course.name)
    ).all()

    courses_by_period: dict[str, list[Course]] = {}
    for course in courses:
        if course.academic_period_id in period_ids:
            courses_by_period.setdefault(course.academic_period_id, []).append(course)

    stages: dict[str, list[Course]] = {}
    for course in courses:
        stages.setdefault(course.learning_stage, []).append(course)

    return {
        "academic_unit": {
            "id": unit.id,
            "name": unit.name,
            "unit_type": unit.unit_type,
        },
        "learning_stages": {stage: [
            {
                "id": course.id,
                "name": course.name,
                "code": course.code,
                "course_type": course.course_type,
                "credit_hours": course.credit_hours,
                "theory_hours": course.theory_hours,
                "practical_hours": course.practical_hours,
                "prerequisites": course.prerequisites,
            }
            for course in items
        ] for stage, items in stages.items()},
        "periods": [
            {
                "id": period.id,
                "name": period.name,
                "kind": period.kind,
                "parent_id": period.parent_id,
                "courses": [
                    {
                        "id": course.id,
                        "name": course.name,
                        "code": course.code,
                        "course_type": course.course_type,
                        "credit_hours": course.credit_hours,
                        "theory_hours": course.theory_hours,
                        "practical_hours": course.practical_hours,
                        "prerequisites": course.prerequisites,
                    }
                    for course in courses_by_period.get(period.id, [])
                ],
            }
            for period in periods
        ],
    }


# ---------------------------------------------------------------------------
# TOFAN-native curriculum catalog management
# ---------------------------------------------------------------------------

from app.db.curriculum_models import (
    Curriculum,
    CurriculumStage,
    CurriculumCourse,
    CurriculumUnit,
    CurriculumLesson,
    Specialty,
    CurriculumStatus,
)


class CurriculumCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=150)
    name: str = Field(min_length=1, max_length=255)
    version: str = Field(min_length=1, max_length=50)
    description: str | None = None


class SpecialtyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=100)
    description: str | None = None
    name_ar: str | None = None
    name_en: str | None = None


class StageCreate(BaseModel):
    curriculum_id: str
    specialty_id: str
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    position: int = Field(ge=1)
    description: str | None = None


class NativeCourseCreate(BaseModel):
    curriculum_id: str
    stage_id: str
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    course_type: str = Field(default="required", max_length=30)
    position: int = Field(ge=1)


class NativeUnitCreate(BaseModel):
    course_id: str
    title: str = Field(min_length=1, max_length=255)
    position: int = Field(ge=1)


class NativeLessonCreate(BaseModel):
    unit_id: str
    title: str = Field(min_length=1, max_length=255)
    position: int = Field(ge=1)
    description: str | None = None
    content_markdown: str | None = None


@router.get("/native/curricula")
def list_native_curricula(
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    return db.scalars(select(Curriculum).order_by(Curriculum.created_at.desc())).all()


@router.post("/native/curricula", status_code=201)
def create_native_curriculum(
    payload: CurriculumCreate,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    item = Curriculum(**payload.model_dump())
    db.add(item)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Curriculum slug/version already exists.")
    db.refresh(item)
    return item


@router.get("/native/specialties")
def list_native_specialties(
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    return db.scalars(select(Specialty).order_by(Specialty.name)).all()


@router.post("/native/specialties", status_code=201)
def create_native_specialty(
    payload: SpecialtyCreate,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    item = Specialty(**payload.model_dump())
    db.add(item)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Specialty code already exists.")
    db.refresh(item)
    return item


@router.get("/native/stages")
def list_native_stages(
    curriculum_id: str,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    return db.scalars(
        select(CurriculumStage)
        .where(CurriculumStage.curriculum_id == curriculum_id)
        .order_by(CurriculumStage.position)
    ).all()


@router.post("/native/stages", status_code=201)
def create_native_stage(
    payload: StageCreate,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    if db.get(Curriculum, payload.curriculum_id) is None:
        raise HTTPException(status_code=404, detail="Curriculum not found.")
    if db.get(Specialty, payload.specialty_id) is None:
        raise HTTPException(status_code=404, detail="Specialty not found.")
    item = CurriculumStage(**payload.model_dump())
    db.add(item)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Stage code already exists for this curriculum.")
    db.refresh(item)
    return item


@router.get("/native/courses")
def list_native_courses(
    stage_id: str,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    return db.scalars(
        select(CurriculumCourse)
        .where(CurriculumCourse.stage_id == stage_id)
        .order_by(CurriculumCourse.position)
    ).all()


@router.post("/native/courses", status_code=201)
def create_native_course(
    payload: NativeCourseCreate,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    stage = db.get(CurriculumStage, payload.stage_id)
    if stage is None or stage.curriculum_id != payload.curriculum_id:
        raise HTTPException(status_code=400, detail="Stage does not belong to the selected curriculum.")
    item = CurriculumCourse(**payload.model_dump())
    db.add(item)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Course code already exists for this curriculum.")
    db.refresh(item)
    return item


@router.get("/native/units")
def list_native_units(
    course_id: str,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    return db.scalars(
        select(CurriculumUnit)
        .where(CurriculumUnit.course_id == course_id)
        .order_by(CurriculumUnit.position)
    ).all()


@router.post("/native/units", status_code=201)
def create_native_unit(
    payload: NativeUnitCreate,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    if db.get(CurriculumCourse, payload.course_id) is None:
        raise HTTPException(status_code=404, detail="Course not found.")
    item = CurriculumUnit(**payload.model_dump())
    db.add(item)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Unit position already exists for this course.")
    db.refresh(item)
    return item


@router.get("/native/lessons")
def list_native_lessons(
    unit_id: str,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    return db.scalars(
        select(CurriculumLesson)
        .where(CurriculumLesson.unit_id == unit_id)
        .order_by(CurriculumLesson.position)
    ).all()


@router.post("/native/lessons", status_code=201)
def create_native_lesson(
    payload: NativeLessonCreate,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    if db.get(CurriculumUnit, payload.unit_id) is None:
        raise HTTPException(status_code=404, detail="Unit not found.")
    item = CurriculumLesson(**payload.model_dump())
    db.add(item)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Lesson position already exists for this unit.")
    db.refresh(item)
    return item




class CurriculumUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    version: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = None
    status: str | None = Field(default=None, max_length=20)


class SpecialtyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    code: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    name_ar: str | None = None
    name_en: str | None = None


class StageUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    position: int | None = Field(default=None, ge=1)


class NativeCourseUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    course_type: str | None = Field(default=None, max_length=30)
    position: int | None = Field(default=None, ge=1)


class NativeUnitUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    position: int | None = Field(default=None, ge=1)


class NativeLessonUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    position: int | None = Field(default=None, ge=1)
    description: str | None = None
    content_markdown: str | None = None


@router.patch("/native/curricula/{curriculum_id}")
def update_native_curriculum(
    curriculum_id: str,
    payload: CurriculumUpdate,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    item = db.get(Curriculum, curriculum_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Curriculum not found.")
    data = payload.model_dump(exclude_unset=True)
    if "status" in data:
        try:
            data["status"] = CurriculumStatus(data["status"])
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid curriculum status.")
    for key, value in data.items():
        setattr(item, key, value)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Curriculum slug/version already exists.")
    db.refresh(item)
    return item


@router.patch("/native/specialties/{specialty_id}")
def update_native_specialty(
    specialty_id: str,
    payload: SpecialtyUpdate,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    item = db.get(Specialty, specialty_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Specialty not found.")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Specialty code already exists.")
    db.refresh(item)
    return item


@router.patch("/native/stages/{stage_id}")
def update_native_stage(
    stage_id: str,
    payload: StageUpdate,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    item = db.get(CurriculumStage, stage_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Stage not found.")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Stage code/position conflicts with another stage.")
    db.refresh(item)
    return item


@router.patch("/native/courses/{course_id}")
def update_native_course(
    course_id: str,
    payload: NativeCourseUpdate,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    item = db.get(CurriculumCourse, course_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Course not found.")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Course code/position conflicts with another course.")
    db.refresh(item)
    return item


@router.patch("/native/units/{unit_id}")
def update_native_unit(
    unit_id: str,
    payload: NativeUnitUpdate,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    item = db.get(CurriculumUnit, unit_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Unit not found.")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Unit position conflicts with another unit.")
    db.refresh(item)
    return item


@router.patch("/native/lessons/{lesson_id}")
def update_native_lesson(
    lesson_id: str,
    payload: NativeLessonUpdate,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    item = db.get(CurriculumLesson, lesson_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Lesson not found.")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Lesson position conflicts with another lesson.")
    db.refresh(item)
    return item


@router.delete("/native/{resource}/{resource_id}", status_code=204)
def delete_native_resource(
    resource: str,
    resource_id: str,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    mapping = {
        "curriculum": Curriculum,
        "specialty": Specialty,
        "stage": CurriculumStage,
        "course": CurriculumCourse,
        "unit": CurriculumUnit,
        "lesson": CurriculumLesson,
    }
    model = mapping.get(resource)
    if model is None:
        raise HTTPException(status_code=400, detail="Unsupported resource.")
    item = db.get(model, resource_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"{resource.capitalize()} not found.")
    db.delete(item)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Cannot delete this resource while it is referenced by other data.")


@router.post("/native/{resource}/{resource_id}/reorder")
def reorder_native_resource(
    resource: str,
    resource_id: str,
    position: int = Field(ge=1),
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    mapping = {
        "stage": CurriculumStage,
        "course": CurriculumCourse,
        "unit": CurriculumUnit,
        "lesson": CurriculumLesson,
    }
    model = mapping.get(resource)
    if model is None:
        raise HTTPException(status_code=400, detail="Only stage/course/unit/lesson can be reordered.")
    item = db.get(model, resource_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"{resource.capitalize()} not found.")

    if resource == "stage":
        siblings = db.scalars(
            select(CurriculumStage)
            .where(CurriculumStage.curriculum_id == item.curriculum_id)
            .order_by(CurriculumStage.position)
        ).all()
    elif resource == "course":
        siblings = db.scalars(
            select(CurriculumCourse)
            .where(CurriculumCourse.stage_id == item.stage_id)
            .order_by(CurriculumCourse.position)
        ).all()
    elif resource == "unit":
        siblings = db.scalars(
            select(CurriculumUnit)
            .where(CurriculumUnit.course_id == item.course_id)
            .order_by(CurriculumUnit.position)
        ).all()
    else:
        siblings = db.scalars(
            select(CurriculumLesson)
            .where(CurriculumLesson.unit_id == item.unit_id)
            .order_by(CurriculumLesson.position)
        ).all()

    siblings = [x for x in siblings if x.id != item.id]
    position = min(position, len(siblings) + 1)

    # Temporarily move the item out of the unique position range, then
    # normalize every sibling so the unique (parent_id, position) constraint
    # remains valid throughout the transaction.
    item.position = 0
    db.flush()
    siblings.insert(position - 1, item)
    for index, sibling in enumerate(siblings, start=1):
        sibling.position = index

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Unable to reorder this item.")
    db.refresh(item)
    return item

@router.patch("/native/{resource}/{resource_id}/active")
def toggle_native_active(
    resource: str,
    resource_id: str,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    if resource == "specialty":
        item = db.get(Specialty, resource_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Specialty not found.")
        item.is_active = not item.is_active
    elif resource == "course":
        item = db.get(CurriculumCourse, resource_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Course not found.")
        item.is_active = not item.is_active
    else:
        raise HTTPException(status_code=400, detail="Unsupported active resource.")
    db.commit()
    db.refresh(item)
    return item
