"""Seed all registered TOFAN global specialty curricula into the academic database.

The JSON registry is the source of truth. The database mirrors the dynamic hierarchy:
Specialty -> Curriculum -> Year/Semester stage -> Course -> Outcomes/Prerequisites.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from app.curriculum_registry import list_curricula, get_curriculum
from app.db.curriculum_models import (
    CoursePrerequisite, Curriculum, CurriculumCourse, CurriculumStage,
    LearningOutcome, Specialty,
)
from app.db.session import SessionLocal

ROOT = Path(__file__).resolve().parents[1]

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
            result.append({"id": raw[0], "name_ar": raw[1], "prerequisites": [], "outcomes": []})
    return result


def seed() -> None:
    with SessionLocal() as db:
        for ref in list_curricula():
            data = get_curriculum(ref.specialty_id)
            ar, en = SPECIALTIES.get(ref.specialty_id, (data.get("title_ar", ref.specialty_id), ref.specialty_id))

            specialty = db.scalar(select(Specialty).where(Specialty.code == ref.specialty_id))
            if specialty is None:
                specialty = Specialty(code=ref.specialty_id)
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
                            position=pos,
                        )
                        db.add(course)
                        db.flush()
                    else:
                        course.stage_id = stage.id
                        course.position = pos
                        course.name = course_data.get("name_ar", course.name)

                    course_map[code] = course

                    existing = {x.position: x for x in db.scalars(
                        select(LearningOutcome).where(LearningOutcome.course_id == course.id)
                    ).all()}
                    outcomes = course_data.get("outcomes") or course_data.get("learning_outcomes") or []
                    for outcome_pos, statement in enumerate(outcomes, start=1):
                        if outcome_pos in existing:
                            existing[outcome_pos].statement = statement
                        else:
                            db.add(LearningOutcome(course_id=course.id, statement=statement, position=outcome_pos))

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

        db.commit()


if __name__ == "__main__":
    seed()
