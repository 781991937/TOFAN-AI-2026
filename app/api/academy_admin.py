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
