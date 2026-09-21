"""TOFAN-native curriculum catalog.

This is the academy's canonical academic structure. Universities are not parents
of this catalog; external institutions remain optional reference/alignment data.
"""

from datetime import datetime
from enum import StrEnum
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base
from .models import new_id

class CurriculumStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"

class Curriculum(Base):
    __tablename__ = "curricula"
    __table_args__ = (UniqueConstraint("slug", "version", name="uq_curriculum_version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(150), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[CurriculumStatus] = mapped_column(default=CurriculumStatus.DRAFT, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

class Specialty(Base):
    __tablename__ = "specialties"
    __table_args__ = (UniqueConstraint("code", name="uq_specialty_code"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    icon: Mapped[str | None] = mapped_column(String(100))
    theme_config_json: Mapped[str | None] = mapped_column(Text)
    name_ar: Mapped[str | None] = mapped_column(String(255))
    name_en: Mapped[str | None] = mapped_column(String(255))
    description_ar: Mapped[str | None] = mapped_column(Text)
    description_en: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

class CurriculumStage(Base):
    __tablename__ = "curriculum_stages"
    __table_args__ = (UniqueConstraint("curriculum_id", "code", name="uq_curriculum_stage_code"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    curriculum_id: Mapped[str] = mapped_column(ForeignKey("curricula.id"), nullable=False)
    specialty_id: Mapped[str] = mapped_column(ForeignKey("specialties.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

class CurriculumEntitlement(Base):
    __tablename__ = "curriculum_entitlements"
    __table_args__ = (
        UniqueConstraint("user_id", "stage_id", name="uq_curriculum_entitlement_user_stage"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    stage_id: Mapped[str] = mapped_column(String(36), ForeignKey("curriculum_stages.id"), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CurriculumCourse(Base):
    __tablename__ = "curriculum_courses"
    __table_args__ = (UniqueConstraint("curriculum_id", "code", name="uq_curriculum_course_code"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    curriculum_id: Mapped[str] = mapped_column(ForeignKey("curricula.id"), nullable=False)
    stage_id: Mapped[str] = mapped_column(ForeignKey("curriculum_stages.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    course_type: Mapped[str] = mapped_column(String(30), default="required", nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

class CoursePrerequisite(Base):
    __tablename__ = "course_prerequisites"
    __table_args__ = (UniqueConstraint("course_id", "prerequisite_course_id", name="uq_course_prerequisite"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_id: Mapped[str] = mapped_column(ForeignKey("curriculum_courses.id"), nullable=False)
    prerequisite_course_id: Mapped[str] = mapped_column(ForeignKey("curriculum_courses.id"), nullable=False)

class LearningOutcome(Base):
    __tablename__ = "learning_outcomes"
    __table_args__ = (UniqueConstraint("course_id", "position", name="uq_course_outcome_position"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_id: Mapped[str] = mapped_column(ForeignKey("curriculum_courses.id"), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

class CurriculumUnit(Base):
    __tablename__ = "curriculum_units"
    __table_args__ = (UniqueConstraint("course_id", "position", name="uq_curriculum_unit_position"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_id: Mapped[str] = mapped_column(ForeignKey("curriculum_courses.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

class CurriculumLesson(Base):
    __tablename__ = "curriculum_lessons"
    __table_args__ = (UniqueConstraint("unit_id", "position", name="uq_curriculum_lesson_position"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    unit_id: Mapped[str] = mapped_column(ForeignKey("curriculum_units.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    content_markdown: Mapped[str | None] = mapped_column(Text)
    source_refs_json: Mapped[str | None] = mapped_column(Text)
    learning_objectives_json: Mapped[str | None] = mapped_column(Text)

class CourseAssessment(Base):
    __tablename__ = "course_assessments"
    __table_args__ = (UniqueConstraint("course_id", "assessment_type", name="uq_course_assessment_type"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_id: Mapped[str] = mapped_column(ForeignKey("curriculum_courses.id"), nullable=False)
    assessment_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    pass_percentage: Mapped[int | None] = mapped_column(Integer)

class CurriculumProject(Base):
    __tablename__ = "curriculum_projects"
    __table_args__ = (UniqueConstraint("curriculum_id", "code", name="uq_curriculum_project_code"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    curriculum_id: Mapped[str] = mapped_column(ForeignKey("curricula.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

class ElectiveTrack(Base):
    __tablename__ = "elective_tracks"
    __table_args__ = (UniqueConstraint("curriculum_id", "name", name="uq_elective_track_name"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    curriculum_id: Mapped[str] = mapped_column(ForeignKey("curricula.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
