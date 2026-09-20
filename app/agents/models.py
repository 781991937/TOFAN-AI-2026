"""Persistent models for TOFAN's AI-agent layer."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models import new_id


class AgentKind(StrEnum):
    ORCHESTRATOR = "orchestrator"
    TEACHER = "teacher"
    SPECIALIST = "specialist"


class AgentStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_agent_slug"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(150), nullable=False)
    kind: Mapped[AgentKind] = mapped_column(nullable=False)
    status: Mapped[AgentStatus] = mapped_column(
        default=AgentStatus.DRAFT, nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text)
    system_prompt: Mapped[str | None] = mapped_column(Text)
    model_provider: Mapped[str | None] = mapped_column(String(100))
    model_name: Mapped[str | None] = mapped_column(String(150))
    memory_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Legacy university-course reference; retained only for backward compatibility.
    teacher_course_id: Mapped[str | None] = mapped_column(ForeignKey("courses.id"))
    # Canonical TOFAN-native academic assignment.
    curriculum_course_id: Mapped[str | None] = mapped_column(ForeignKey("curriculum_courses.id"))
    # Optional external university/reference alignment; never the academic parent.
    teacher_institution_id: Mapped[str | None] = mapped_column(ForeignKey("institutions.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
        onupdate=datetime.utcnow, nullable=False
    )


class AgentTool(Base):
    __tablename__ = "agent_tools"
    __table_args__ = (
        UniqueConstraint("agent_id", "tool_name", name="uq_agent_tool"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(150), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    tool_name: Mapped[str | None] = mapped_column(String(150))
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    input_text: Mapped[str | None] = mapped_column(Text)
    output_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
