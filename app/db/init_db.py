"""Create the initial database schema."""

from .base import Base
from .models import (
    AcademicPeriod, AcademicUnit, AuditLog, AuthSession,
    BiometricCredentialRecord, ContentFile, Course, Entitlement,
    Institution, Lecture, OtpChallenge, Unit, User, UserCredential,
)
from .session import engine
from .migrations import run_migrations
from app.auth.models import UserRole  # noqa: F401
from app.agents.models import Agent, AgentRun, AgentTool  # noqa: F401
from app.agents.memory import AgentConversation, AgentMessageRecord  # noqa: F401


def init_db() -> None:
    Base.metadata.create_all(bind=engine)\n    run_migrations(engine)


if __name__ == "__main__":
    init_db()
