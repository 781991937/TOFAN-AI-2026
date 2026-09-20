"""Core dynamic academic and access models.

The hierarchy is intentionally data-driven: no fixed number of universities,
programs, specializations, courses, units, or lectures is encoded in Python.
"""

from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def new_id() -> str:
    return str(uuid4())


class ContentStatus(StrEnum):
    FREE = "free"
    PAID = "paid"
    PRIVATE = "private"
    DRAFT = "draft"


class Institution(Base):
    __tablename__ = "institutions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str | None] = mapped_column(String(100), unique=True)
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
    original_name: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    mime_type: Mapped[str | None] = mapped_column(String(150))
    status: Mapped[ContentStatus] = mapped_column(default=ContentStatus.DRAFT, nullable=False)
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


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(100))
    resource_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    details: Mapped[str | None] = mapped_column(Text)
