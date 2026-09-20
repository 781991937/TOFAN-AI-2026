"""Persistent academic mastery progress for TOFAN students."""

from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base
from .models import new_id


class LearningProgress(Base):
    __tablename__ = "learning_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "course_id", "lesson_id", name="uq_learning_progress_lesson"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    course_id: Mapped[str] = mapped_column(ForeignKey("curriculum_courses.id"), nullable=False)
    lesson_id: Mapped[str | None] = mapped_column(ForeignKey("curriculum_lessons.id"))
    status: Mapped[str] = mapped_column(String(30), default="not_started", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    understanding_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    assessment_percentage: Mapped[float | None] = mapped_column(Float)
    last_score: Mapped[float | None] = mapped_column(Float)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class LearningWeakPoint(Base):
    __tablename__ = "learning_weak_points"
    __table_args__ = (
        UniqueConstraint("user_id", "course_id", "lesson_id", "topic", name="uq_learning_weak_point"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    course_id: Mapped[str] = mapped_column(ForeignKey("curriculum_courses.id"), nullable=False)
    lesson_id: Mapped[str | None] = mapped_column(ForeignKey("curriculum_lessons.id"))
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    occurrences: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class LearningNextStep(Base):
    __tablename__ = "learning_next_steps"
    __table_args__ = (
        UniqueConstraint("user_id", "course_id", name="uq_learning_next_step_course"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    course_id: Mapped[str] = mapped_column(ForeignKey("curriculum_courses.id"), nullable=False)
    lesson_id: Mapped[str | None] = mapped_column(ForeignKey("curriculum_lessons.id"))
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
