"""Student onboarding, profile verification, and payment approval models."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .models import new_id


class UserType(StrEnum):
    UNIVERSITY_STUDENT = "university_student"
    INDEPENDENT_LEARNER = "independent_learner"


class ProfileStatus(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    BLOCKED = "blocked"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class StudentProfile(Base):
    __tablename__ = "student_profiles"
    __table_args__ = (UniqueConstraint("user_id", name="uq_student_profile_user"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    user_type: Mapped[UserType] = mapped_column(
        default=UserType.INDEPENDENT_LEARNER, nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    age: Mapped[int | None] = mapped_column(Integer)
    institution_id: Mapped[str | None] = mapped_column(ForeignKey("institutions.id"))
    college_unit_id: Mapped[str | None] = mapped_column(ForeignKey("academic_units.id"))
    major_unit_id: Mapped[str | None] = mapped_column(ForeignKey("academic_units.id"))
    profile_status: Mapped[ProfileStatus] = mapped_column(
        default=ProfileStatus.PENDING, nullable=False
    )
    biometric_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
        onupdate=datetime.utcnow, nullable=False
    )


class PaymentAccountSetting(Base):
    __tablename__ = "payment_account_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    provider_name: Mapped[str] = mapped_column(String(100), nullable=False)
    account_name: Mapped[str | None] = mapped_column(String(255))
    account_number: Mapped[str] = mapped_column(String(100), nullable=False)
    instructions: Mapped[str | None] = mapped_column(String(1000))
    currency: Mapped[str | None] = mapped_column(String(20))
    amount: Mapped[float | None] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    product_key: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        default=PaymentStatus.PENDING, nullable=False
    )
    amount: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str | None] = mapped_column(String(20))
    reference: Mapped[str | None] = mapped_column(String(255))
    proof_file_id: Mapped[str | None] = mapped_column(ForeignKey("content_files.id"))
    rejection_reason: Mapped[str | None] = mapped_column(String(500))
    confirmed_by_agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
