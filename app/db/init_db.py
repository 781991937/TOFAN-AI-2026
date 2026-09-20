"""Create the initial database schema."""

from .base import Base
from .models import (
    AcademicPeriod, AcademicUnit, AuditLog, AuthSession,
    BiometricCredentialRecord, ContentFile, Course, Entitlement,
    Institution, Lecture, OtpChallenge, Unit, User, UserCredential,
    TeachingUsage, TeachingStep, TeachingAssessment, TeachingAssessmentReport,
)
from .identity_models import StudentProfile, PaymentTransaction
from .assessment_models import CurriculumAssessmentAttempt, AssessmentResultReport
from .curriculum_models import Curriculum, Specialty, CurriculumStage, CurriculumCourse, CoursePrerequisite, LearningOutcome, CurriculumUnit, CurriculumLesson, CourseAssessment, CurriculumProject, ElectiveTrack
from .session import engine
from .migrations import run_migrations
from app.auth.models import UserRole
from app.agents.models import Agent, AgentRun, AgentTool
from app.agents.memory import AgentConversation, AgentMemoryItem, AgentMemoryPermission, AgentMessageRecord
from scripts.seed_tofan_curriculum import seed as seed_tofan_curriculum


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    run_migrations(engine)
    seed_tofan_curriculum()


if __name__ == "__main__":
    init_db()
