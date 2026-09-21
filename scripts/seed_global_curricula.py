"""Seed all registered TOFAN global specialty curricula into the academic database.

The registry is the source of truth. Legacy curriculum files are normalized by
app.curriculum_registry before reaching this seeder.
"""

from __future__ import annotations

import json

from sqlalchemy import select

from app.curriculum_registry import get_curriculum, list_curricula
from app.db.curriculum_models import (
    CourseAssessment,
    CoursePrerequisite,
    Curriculum,
    CurriculumCourse,
    CurriculumLesson,
    CurriculumProject,
    CurriculumStage,
    CurriculumUnit,
    ElectiveTrack,
    LearningOutcome,
    Specialty,
)
from app.db.session import SessionLocal


SPECIALTIES = {
    "AI": ("الذكاء الاصطناعي", "Artificial Intelligence"),
    "CS": ("علوم الحاسوب", "Computer Science"),
    "CYBER": ("الأمن السيبراني", "Cybersecurity"),
    "SE": ("هندسة البرمجيات", "Software Engineering"),
    "DS": ("علم البيانات", "Data Science"),
}


def _courses(semester: dict) -> list[dict]:
    result = []
    for raw in semester.get("courses", []):
        if isinstance(raw, dict):
            result.append(raw)
        elif isinstance(raw, list) and len(raw) >= 2:
            result.append({
                "id": raw[0],
                "name_ar": raw[1],
                "prerequisites": [],
                "outcomes": [],
            })
    return result


def _upsert_outcomes(db, course, outcomes: list[str]) -> None:
    existing = {
        x.position: x
        for x in db.scalars(
            select(LearningOutcome).where(LearningOutcome.course_id == course.id)
        ).all()
    }
    for position, statement in enumerate(outcomes, start=1):
        if position in existing:
            existing[position].statement = statement
        else:
            db.add(LearningOutcome(
                course_id=course.id,
                statement=statement,
                position=position,
            ))


def _seed_units_lessons_assessments(db, course, course_data: dict) -> None:
    units = course_data.get("units") or []
    for unit_pos, raw_unit in enumerate(units, start=1):
        if isinstance(raw_unit, str):
            unit_title = raw_unit
            lessons = []
        else:
            unit_title = raw_unit.get("title_ar") or raw_unit.get("name_ar") or raw_unit.get("title") or f"الوحدة {unit_pos}"
            lessons = raw_unit.get("lessons") or []

        unit = db.scalar(select(CurriculumUnit).where(
            CurriculumUnit.course_id == course.id,
            CurriculumUnit.position == unit_pos,
        ))
        if unit is None:
            unit = CurriculumUnit(course_id=course.id, title=unit_title, position=unit_pos)
            db.add(unit)
            db.flush()
        else:
            unit.title = unit_title

        for lesson_pos, raw_lesson in enumerate(lessons, start=1):
            if isinstance(raw_lesson, str):
                title = raw_lesson
                description = None
                content = None
                objectives = None
                source_refs = None
            else:
                title = raw_lesson.get("title_ar") or raw_lesson.get("name_ar") or raw_lesson.get("title") or f"الدرس {lesson_pos}"
                description = raw_lesson.get("description_ar") or raw_lesson.get("description")
                content = raw_lesson.get("content_markdown")
                objectives = json.dumps(raw_lesson.get("learning_objectives", []), ensure_ascii=False) if raw_lesson.get("learning_objectives") else None
                source_refs = json.dumps(raw_lesson.get("source_refs", []), ensure_ascii=False) if raw_lesson.get("source_refs") else None

            lesson = db.scalar(select(CurriculumLesson).where(
                CurriculumLesson.unit_id == unit.id,
                CurriculumLesson.position == lesson_pos,
            ))
            if lesson is None:
                db.add(CurriculumLesson(
                    unit_id=unit.id,
                    title=title,
                    position=lesson_pos,
                    description=description,
                    content_markdown=content,
                    learning_objectives_json=objectives,
                    source_refs_json=source_refs,
                ))
            else:
                lesson.title = title
                lesson.description = description
                lesson.content_markdown = content
                lesson.learning_objectives_json = objectives
                lesson.source_refs_json = source_refs

    assessment = course_data.get("assessment")
    if assessment:
        items = assessment if isinstance(assessment, list) else [assessment]
        for item in items:
            if isinstance(item, str):
                assessment_type = "course"
                title = item
                description = None
                pass_percentage = None
            else:
                assessment_type = item.get("type") or item.get("assessment_type") or "course"
                title = item.get("title_ar") or item.get("title") or "تقييم المقرر"
                description = item.get("description_ar") or item.get("description")
                pass_percentage = item.get("pass_percentage")
            row = db.scalar(select(CourseAssessment).where(
                CourseAssessment.course_id == course.id,
                CourseAssessment.assessment_type == assessment_type,
            ))
            if row is None:
                db.add(CourseAssessment(
                    course_id=course.id,
                    assessment_type=assessment_type,
                    title=title,
                    description=description,
                    pass_percentage=pass_percentage,
                ))
            else:
                row.title = title
                row.description = description
                row.pass_percentage = pass_percentage


def seed() -> None:
    with SessionLocal() as db:
        for ref in list_curricula():
            data = get_curriculum(ref.specialty_id)
            ar, en = SPECIALTIES.get(
                ref.specialty_id,
                (data.get("title_ar", ref.specialty_id), data.get("title_en", ref.specialty_id)),
            )

            specialty = db.scalar(select(Specialty).where(Specialty.code == ref.specialty_id))
            if specialty is None:
                specialty = Specialty(code=ref.specialty_id, name=ar)
                db.add(specialty)
                db.flush()
            specialty.name = ar
            specialty.name_ar = ar
            specialty.name_en = en
            specialty.description = data.get("title_ar")
            specialty.description_ar = data.get("title_ar")
            specialty.description_en = data.get("title_en")

            curriculum = db.scalar(select(Curriculum).where(
                Curriculum.slug == ref.curriculum_id,
                Curriculum.version == data.get("version", "1.0"),
            ))
            if curriculum is None:
                curriculum = Curriculum(
                    slug=ref.curriculum_id,
                    name=data.get("title_ar", ar),
                    version=data.get("version", "1.0"),
                    status="active",
                    description="Canonical TOFAN global specialty curriculum.",
                )
                db.add(curriculum)
                db.flush()
            else:
                curriculum.name = data.get("title_ar", ar)
                curriculum.status = "active"
                curriculum.description = "Canonical TOFAN global specialty curriculum."

            course_map = {}
            for semester in data.get("semesters", []):
                year = int(semester["year_number"])
                sem = int(semester["semester_number"])
                stage_code = f"Y{year}S{sem}"
                stage = db.scalar(select(CurriculumStage).where(
                    CurriculumStage.curriculum_id == curriculum.id,
                    CurriculumStage.code == stage_code,
                ))
                if stage is None:
                    stage = CurriculumStage(
                        curriculum_id=curriculum.id,
                        specialty_id=specialty.id,
                        code=stage_code,
                        name=semester.get("title_ar", f"السنة {year} — الفصل {sem}"),
                        position=(year - 1) * 2 + sem,
                        description=semester.get("focus_ar"),
                    )
                    db.add(stage)
                    db.flush()
                else:
                    stage.name = semester.get("title_ar", stage.name)
                    stage.position = (year - 1) * 2 + sem
                    stage.description = semester.get("focus_ar")

                for pos, course_data in enumerate(_courses(semester), start=1):
                    code = course_data["id"]
                    course = db.scalar(select(CurriculumCourse).where(
                        CurriculumCourse.curriculum_id == curriculum.id,
                        CurriculumCourse.code == code,
                    ))
                    if course is None:
                        course = CurriculumCourse(
                            curriculum_id=curriculum.id,
                            stage_id=stage.id,
                            code=code,
                            name=course_data.get("name_ar", code),
                            description=course_data.get("description_ar"),
                            position=pos,
                        )
                        db.add(course)
                        db.flush()
                    else:
                        course.stage_id = stage.id
                        course.position = pos
                        course.name = course_data.get("name_ar", course.name)
                        course.description = course_data.get("description_ar")
                        course.is_active = True

                    course_map[code] = course
                    outcomes = course_data.get("outcomes") or course_data.get("learning_outcomes") or []
                    _upsert_outcomes(db, course, outcomes)
                    _seed_units_lessons_assessments(db, course, course_data)

            db.flush()

            for semester in data.get("semesters", []):
                for course_data in _courses(semester):
                    course = course_map[course_data["id"]]
                    for prereq_code in course_data.get("prerequisites", []):
                        prerequisite = course_map.get(prereq_code)
                        if prerequisite is None:
                            continue
                        exists = db.scalar(select(CoursePrerequisite).where(
                            CoursePrerequisite.course_id == course.id,
                            CoursePrerequisite.prerequisite_course_id == prerequisite.id,
                        ))
                        if exists is None:
                            db.add(CoursePrerequisite(
                                course_id=course.id,
                                prerequisite_course_id=prerequisite.id,
                            ))

            for project in data.get("capstone_projects", []) + data.get("projects", []):
                if not isinstance(project, dict) or not project.get("id"):
                    continue
                row = db.scalar(select(CurriculumProject).where(
                    CurriculumProject.curriculum_id == curriculum.id,
                    CurriculumProject.code == project["id"],
                ))
                description = "؛ ".join(project.get("outcomes", [])) or project.get("description_ar") or project.get("description")
                if row is None:
                    db.add(CurriculumProject(
                        curriculum_id=curriculum.id,
                        code=project["id"],
                        name=project.get("name_ar", project["id"]),
                        description=description,
                    ))
                else:
                    row.name = project.get("name_ar", row.name)
                    row.description = description

            for track in data.get("elective_tracks", []):
                name = track if isinstance(track, str) else track.get("name_ar") or track.get("name")
                if not name:
                    continue
                row = db.scalar(select(ElectiveTrack).where(
                    ElectiveTrack.curriculum_id == curriculum.id,
                    ElectiveTrack.name == name,
                ))
                if row is None:
                    db.add(ElectiveTrack(
                        curriculum_id=curriculum.id,
                        name=name,
                        description=None if isinstance(track, str) else track.get("description_ar"),
                    ))

        db.commit()


if __name__ == "__main__":
    seed()
