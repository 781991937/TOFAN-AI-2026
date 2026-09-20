"""Core dynamic academy, reference, and access models.

TOFAN-native curricula are independent from university curricula. University
structures can be stored as references without becoming the academy's required
learning model.
"""

from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def new_id() -> str:
    return str(uuid4())


class ContentStatus(StrEnum):
    FREE = "free"
    PAID = "paid"
    PRIVATE = "private"
    DRAFT = "draft"


class TeachingSource(StrEnum):
    STUDENT_FILES = "student_files"
    GLOBAL_CURRICULUM = "global_curriculum"


class TeachingAccess(StrEnum):
    FREE = "free"
    PAID = "paid"


class AcademyAccessTier(StrEnum):
    FREE = "free"
    PAID = "paid"


class TeachingStepStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"


class OrganizationType(StrEnum):
    ACADEMY = "academy"
    UNIVERSITY = "university"
    COLLEGE = "college"
    CENTER = "center"
    REFERENCE = "reference"


class LearningStage(StrEnum):
    FOUNDATION = "foundation"
    LEVEL = "level"
    TRACK = "track"
    PROJECT = "project"
    ELECTIVE = "elective"


class Institution(Base):
    __tablename__ = "institutions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str | None] = mapped_column(String(100), unique=True)
    organization_type: Mapped[str] = mapped_column(
        String(30), default=OrganizationType.UNIVERSITY, nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    units: Mapped[list["AcademicUnit"]] = relationship(
        back_populates="institution", cascade="all, delete-orphan"
    )


class AcademicUnit(Base):
    __tablename__ = "academic_units"
    __table_args__ = (
        UniqueConstraint("institution_id", "parent_id", "name", name="uq_academic_unit_sibling_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("academic_units.id"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    institution: Mapped["Institution"] = relationship(back_populates="units")
    parent: Mapped["AcademicUnit | None"] = relationship(
        remote_side=[id], back_populates="children"
    )
    children: Mapped[list["AcademicUnit"]] = relationship(
        back_populates="parent", cascade="all, delete-orphan"
    )


class AcademicPeriod(Base):
    __tablename__ = "academic_periods"
    __table_args__ = (
        UniqueConstraint("institution_id", "name", name="uq_academic_period"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("academic_periods.id"))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    year_number: Mapped[int | None] = mapped_column(Integer)
    term_number: Mapped[int | None] = mapped_column(Integer)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    parent: Mapped["AcademicPeriod | None"] = relationship(remote_side=[id])


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    academic_unit_id: Mapped[str] = mapped_column(ForeignKey("academic_units.id"), nullable=False)
    academic_period_id: Mapped[str | None] = mapped_column(ForeignKey("academic_periods.id"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    course_type: Mapped[str] = mapped_column(String(30), default="required", nullable=False)
    learning_stage: Mapped[str] = mapped_column(
        String(30), default=LearningStage.FOUNDATION, nullable=False
    )
    credit_hours: Mapped[int | None] = mapped_column(Integer)
    theory_hours: Mapped[int | None] = mapped_column(Integer)
    practical_hours: Mapped[int | None] = mapped_column(Integer)
    prerequisites: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Unit(Base):
    __tablename__ = "course_units"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[int] = mapped_column(nullable=False)


class Lecture(Base):
    __tablename__ = "lectures"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    unit_id: Mapped[str] = mapped_column(ForeignKey("course_units.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[ContentStatus] = mapped_column(default=ContentStatus.DRAFT, nullable=False)


class ContentFile(Base):
    __tablename__ = "content_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    lecture_id: Mapped[str | None] = mapped_column(ForeignKey("lectures.id"))
    uploaded_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    teaching_agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"))
    teaching_source: Mapped[TeachingSource | None] = mapped_column(String(40))
    original_name: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    extracted_text: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    page_count: Mapped[int | None] = mapped_column(Integer)
    mime_type: Mapped[str | None] = mapped_column(String(150))
    status: Mapped[ContentStatus] = mapped_column(default=ContentStatus.DRAFT, nullable=False)
    assessment_json: Mapped[str | None] = mapped_column(Text)
    assessment_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    display_name: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(320), unique=True)
    phone: Mapped[str | None] = mapped_column(String(50), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class UserCredential(Base):
    __tablename__ = "user_credentials"
    __table_args__ = (
        UniqueConstraint("provider", "provider_subject", name="uq_user_provider_subject"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_subject: Mapped[str] = mapped_column(String(500), nullable=False)
    secret_hash: Mapped[str | None] = mapped_column(Text)


class PasskeyChallenge(Base):
    __tablename__ = "passkey_challenges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    purpose: Mapped[str] = mapped_column(String(40), nullable=False)
    state_json: Mapped[str] = mapped_column(Text, nullable=False)
    device_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BiometricCredentialRecord(Base):
    __tablename__ = "biometric_credentials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    device_id: Mapped[str] = mapped_column(String(255), nullable=False)
    credential_id: Mapped[str] = mapped_column(String(1000), unique=True, nullable=False)
    public_key: Mapped[str] = mapped_column(Text, nullable=False)
    sign_count: Mapped[int] = mapped_column(default=0, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    device_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OtpChallenge(Base):
    __tablename__ = "otp_challenges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    destination: Mapped[str] = mapped_column(String(320), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Entitlement(Base):
    __tablename__ = "entitlements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    content_file_id: Mapped[str | None] = mapped_column(ForeignKey("content_files.id"))
    lecture_id: Mapped[str | None] = mapped_column(ForeignKey("lectures.id"))
    access_type: Mapped[str] = mapped_column(String(50), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))




class TeachingUsage(Base):
    __tablename__ = "teaching_usage"
    __table_args__ = (
        UniqueConstraint("user_id", "agent_id", "source", name="uq_teaching_usage_user_agent_source"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False)
    source: Mapped[TeachingSource] = mapped_column(String(40), nullable=False)
    files_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    files_limit: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    free_steps_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    free_steps_limit: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    response_chars_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    response_chars_limit: Mapped[int] = mapped_column(Integer, default=2000, nullable=False)
    quota_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_access: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class TeachingStep(Base):
    __tablename__ = "teaching_steps"
    __table_args__ = (
        UniqueConstraint("user_id", "agent_id", "source", "scope_key", "position", name="uq_teaching_step"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False)
    source: Mapped[TeachingSource] = mapped_column(String(40), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(500), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[TeachingStepStatus] = mapped_column(default=TeachingStepStatus.ACTIVE, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    understanding_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    student_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TeachingAssessment(Base):
    __tablename__ = "teaching_assessments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False)
    content_file_id: Mapped[str] = mapped_column(ForeignKey("content_files.id"), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    max_score: Mapped[float] = mapped_column(Float, nullable=False)
    percentage: Mapped[float] = mapped_column(Float, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class TeachingAssessmentReport(Base):
    __tablename__ = "teaching_assessment_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("teaching_assessments.id"), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(100))
    resource_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    details: Mapped[str | None] = mapped_column(Text)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("id", name="uq_notification_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(100))
    resource_id: Mapped[str | None] = mapped_column(String(255))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
