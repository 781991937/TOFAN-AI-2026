"""Public TOFAN-native curriculum catalog endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_db
from app.curriculum_registry import CurriculumError, get_curriculum, list_curricula, semester_courses
from app.db.curriculum_models import (
    CoursePrerequisite, Curriculum, CurriculumCourse, CurriculumLesson,
    CurriculumProject, CurriculumStage, CurriculumUnit, ElectiveTrack,
    LearningOutcome, Specialty,
)

router = APIRouter(prefix="/curriculum", tags=["curriculum"])


@router.get("/registry/specialties")
def list_registry_specialties():
    result = []
    for ref in list_curricula():
        curriculum = get_curriculum(ref.specialty_id)
        result.append({
            "specialty_id": ref.specialty_id,
            "curriculum_id": ref.curriculum_id,
            "name_ar": curriculum.get("name_ar"),
            "name_en": curriculum.get("name_en"),
            "description_ar": curriculum.get("description_ar"),
            "description_en": curriculum.get("description_en"),
            "years": 4,
            "semesters_per_year": 2,
        })
    return result


@router.get("/registry/{specialty_id}")
def get_registry_curriculum(specialty_id: str):
    try:
        return get_curriculum(specialty_id)
    except CurriculumError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/registry/{specialty_id}/{year}/{semester}")
def get_registry_semester_courses(specialty_id: str, year: int, semester: int):
    try:
        courses = semester_courses(specialty_id, year, semester)
    except CurriculumError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"specialty_id": specialty_id, "year": year, "semester": semester, "courses": courses}


@router.get("/specialties")
def list_specialties(db: Session = Depends(get_db)):
    rows = db.scalars(select(Specialty).where(Specialty.is_active.is_(True)).order_by(Specialty.name)).all()
    return [{"id": x.id, "code": x.code, "name": x.name} for x in rows]


@router.get("/courses/{course_id}")
def get_curriculum_course(course_id: str, db: Session = Depends(get_db)):
    course = db.get(CurriculumCourse, course_id)
    if course is None or not course.is_active:
        raise HTTPException(status_code=404, detail="TOFAN curriculum course not found.")

    stage = db.get(CurriculumStage, course.stage_id)
    outcomes = db.scalars(select(LearningOutcome).where(LearningOutcome.course_id == course.id).order_by(LearningOutcome.position)).all()
    prerequisites = db.scalars(select(CoursePrerequisite).where(CoursePrerequisite.course_id == course.id)).all()
    units = db.scalars(select(CurriculumUnit).where(CurriculumUnit.course_id == course.id).order_by(CurriculumUnit.position)).all()

    result_units = []
    for unit in units:
        lessons = db.scalars(select(CurriculumLesson).where(CurriculumLesson.unit_id == unit.id).order_by(CurriculumLesson.position)).all()
        result_units.append({
            "id": unit.id, "title": unit.title, "position": unit.position,
            "lessons": [
                {"id": l.id, "title": l.title, "position": l.position, "description": l.description,
                 "has_content": bool((l.content_markdown or "").strip())}
                for l in lessons
            ],
        })

    return {
        "id": course.id, "code": course.code, "name": course.name,
        "description": course.description, "course_type": course.course_type, "position": course.position,
        "stage": {"id": stage.id, "code": stage.code, "name": stage.name, "position": stage.position} if stage else None,
        "outcomes": [x.statement for x in outcomes],
        "prerequisite_course_ids": [x.prerequisite_course_id for x in prerequisites],
        "units": result_units,
    }


@router.get("/{curriculum_slug}")
def get_db_curriculum(curriculum_slug: str, db: Session = Depends(get_db)):
    curriculum = db.scalar(
        select(Curriculum).where(
            Curriculum.slug == curriculum_slug,
            Curriculum.status == "active",
        )
    )
    if curriculum is None:
        raise HTTPException(status_code=404, detail="Curriculum not found.")

    stages = db.scalars(
        select(CurriculumStage)
        .where(CurriculumStage.curriculum_id == curriculum.id)
        .order_by(CurriculumStage.position)
    ).all()

    semesters = []
    for stage in stages:
        courses = db.scalars(
            select(CurriculumCourse)
            .where(
                CurriculumCourse.stage_id == stage.id,
                CurriculumCourse.is_active.is_(True),
            )
            .order_by(CurriculumCourse.position)
        ).all()

        result_courses = []
        for course in courses:
            outcomes = db.scalars(
                select(LearningOutcome)
                .where(LearningOutcome.course_id == course.id)
                .order_by(LearningOutcome.position)
            ).all()
            prerequisites = db.scalars(
                select(CoursePrerequisite)
                .where(CoursePrerequisite.course_id == course.id)
            ).all()
            units = db.scalars(
                select(CurriculumUnit)
                .where(CurriculumUnit.course_id == course.id)
                .order_by(CurriculumUnit.position)
            ).all()

            result_units = []
            for unit in units:
                lessons = db.scalars(
                    select(CurriculumLesson)
                    .where(CurriculumLesson.unit_id == unit.id)
                    .order_by(CurriculumLesson.position)
                ).all()
                result_units.append({
                    "id": unit.id,
                    "title": unit.title,
                    "position": unit.position,
                    "lessons": [
                        {
                            "id": lesson.id,
                            "title": lesson.title,
                            "position": lesson.position,
                            "description": lesson.description,
                            "has_content": bool((lesson.content_markdown or "").strip()),
                        }
                        for lesson in lessons
                    ],
                })

            result_courses.append({
                "id": course.id,
                "code": course.code,
                "name": course.name,
                "description": course.description,
                "course_type": course.course_type,
                "position": course.position,
                "outcomes": [x.statement for x in outcomes],
                "prerequisite_course_ids": [x.prerequisite_course_id for x in prerequisites],
                "units": result_units,
            })

        code_parts = stage.code.removeprefix("Y")
        try:
            year_text, semester_text = code_parts.split("S", 1)
            year = int(year_text)
            semester = int(semester_text)
        except (ValueError, AttributeError):
            year = None
            semester = None

        semesters.append({
            "id": stage.id,
            "code": stage.code,
            "year": year,
            "semester": semester,
            "name": stage.name,
            "position": stage.position,
            "courses": result_courses,
        })

    projects = db.scalars(
        select(CurriculumProject)
        .where(CurriculumProject.curriculum_id == curriculum.id)
        .order_by(CurriculumProject.code)
    ).all()
    tracks = db.scalars(
        select(ElectiveTrack)
        .where(ElectiveTrack.curriculum_id == curriculum.id)
        .order_by(ElectiveTrack.name)
    ).all()

    return {
        "id": curriculum.id,
        "slug": curriculum.slug,
        "name": curriculum.name,
        "version": curriculum.version,
        "structure": {
            "years": 4,
            "semesters_per_year": 2,
            "total_semesters": 8,
        },
        "semesters": semesters,
        "projects": [
            {"id": x.id, "code": x.code, "name": x.name, "description": x.description}
            for x in projects
        ],
        "elective_tracks": [
            {"id": x.id, "name": x.name, "description": x.description}
            for x in tracks
        ],
    }
