"""Seed the canonical TOFAN AI curriculum from the approved JSON document.

Safe to run repeatedly: existing rows are matched by stable curriculum/course/stage
codes and are not duplicated.
"""

import json
from pathlib import Path

from sqlalchemy import select

from app.db.curriculum_models import (
    CoursePrerequisite, Curriculum, CurriculumCourse, CurriculumProject,
    CurriculumStage, ElectiveTrack, LearningOutcome, Specialty,
)
from app.db.session import SessionLocal

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "curricula" / "ai_tofan_curriculum_v1.json"


def seed() -> None:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    with SessionLocal() as db:
        curriculum = db.scalar(
            select(Curriculum).where(
                Curriculum.slug == data["curriculum_id"],
                Curriculum.version == data["version"],
            )
        )
        if curriculum is None:
            curriculum = Curriculum(
                slug=data["curriculum_id"],
                name=data["title_ar"],
                version=data["version"],
                status="active",
                description="Canonical TOFAN-native AI curriculum.",
            )
            db.add(curriculum)
            db.flush()

        specialty = db.scalar(
            select(Specialty).where(Specialty.code == "AI")
        )
        if specialty is None:
            specialty = Specialty(
                code="AI",
                name="الذكاء الاصطناعي",
                description="TOFAN global AI specialization.",
            )
            db.add(specialty)
            db.flush()

        course_map = {}
        for stage_position, stage_data in enumerate(data["stages"], start=1):
            stage = db.scalar(
                select(CurriculumStage).where(
                    CurriculumStage.curriculum_id == curriculum.id,
                    CurriculumStage.code == stage_data["id"],
                )
            )
            if stage is None:
                stage = CurriculumStage(
                    curriculum_id=curriculum.id,
                    specialty_id=specialty.id,
                    code=stage_data["id"],
                    name=stage_data["name_ar"],
                    position=stage_position,
                )
                db.add(stage)
                db.flush()

            for course_position, course_data in enumerate(stage_data["courses"], start=1):
                course = db.scalar(
                    select(CurriculumCourse).where(
                        CurriculumCourse.curriculum_id == curriculum.id,
                        CurriculumCourse.code == course_data["id"],
                    )
                )
                if course is None:
                    course = CurriculumCourse(
                        curriculum_id=curriculum.id,
                        stage_id=stage.id,
                        code=course_data["id"],
                        name=course_data["name_ar"],
                        position=course_position,
                    )
                    db.add(course)
                    db.flush()
                course_map[course.code] = course

                existing_outcomes = {
                    row.position: row
                    for row in db.scalars(
                        select(LearningOutcome).where(LearningOutcome.course_id == course.id)
                    ).all()
                }
                for pos, statement in enumerate(course_data.get("outcomes", []), start=1):
                    if pos not in existing_outcomes:
                        db.add(LearningOutcome(
                            course_id=course.id,
                            statement=statement,
                            position=pos,
                        ))

        db.flush()

        for stage_data in data["stages"]:
            for course_data in stage_data["courses"]:
                course = course_map[course_data["id"]]
                for prerequisite_code in course_data.get("prerequisites", []):
                    prerequisite = course_map.get(prerequisite_code)
                    if prerequisite is None:
                        continue
                    exists = db.scalar(
                        select(CoursePrerequisite).where(
                            CoursePrerequisite.course_id == course.id,
                            CoursePrerequisite.prerequisite_course_id == prerequisite.id,
                        )
                    )
                    if exists is None:
                        db.add(CoursePrerequisite(
                            course_id=course.id,
                            prerequisite_course_id=prerequisite.id,
                        ))

        for project in data.get("capstone_projects", []):
            exists = db.scalar(
                select(CurriculumProject).where(
                    CurriculumProject.curriculum_id == curriculum.id,
                    CurriculumProject.code == project["id"],
                )
            )
            if exists is None:
                db.add(CurriculumProject(
                    curriculum_id=curriculum.id,
                    code=project["id"],
                    name=project["name_ar"],
                    description="; ".join(project.get("outcomes", [])),
                ))

        for track_name in data.get("elective_tracks", []):
            exists = db.scalar(
                select(ElectiveTrack).where(
                    ElectiveTrack.curriculum_id == curriculum.id,
                    ElectiveTrack.name == track_name,
                )
            )
            if exists is None:
                db.add(ElectiveTrack(
                    curriculum_id=curriculum.id,
                    name=track_name,
                ))

        db.commit()


if __name__ == "__main__":
    seed()
