"""Create the initial database schema and bootstrap core catalog data."""

from .base import Base
from .models import (
    AcademicPeriod, AcademicUnit, AuditLog, AuthSession,
    BiometricCredentialRecord, ContentFile, Course, Entitlement,
    Institution, Lecture, OtpChallenge, Unit, User, UserCredential,
    TeachingUsage, TeachingStep, TeachingAssessment, TeachingAssessmentReport,
)
from .identity_models import StudentProfile, PaymentTransaction, PaymentAccountSetting
from .assessment_models import CurriculumAssessmentAttempt, AssessmentResultReport
from .assessment_question_models import CurriculumAssessmentQuestion
from .curriculum_models import Curriculum, Specialty, CurriculumStage, CurriculumCourse, CurriculumEntitlement, CoursePrerequisite, LearningOutcome, CurriculumUnit, CurriculumLesson, CourseAssessment, CurriculumProject, ElectiveTrack
from .session import engine
from .migrations import run_migrations
from app.auth.models import UserRole
from app.agents.models import Agent, AgentRun, AgentTool
from app.agents.memory import AgentConversation, AgentMemoryItem, AgentMemoryPermission, AgentMessageRecord
from scripts.seed_tofan_curriculum import seed as seed_tofan_curriculum
from scripts.seed_global_curricula import seed as seed_global_curricula
from scripts.bootstrap_tofan_academy import main as bootstrap_tofan_academy
from scripts.bootstrap_sanaa_university import main as bootstrap_sanaa_university


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    run_migrations(engine)
    bootstrap_tofan_academy()
    bootstrap_sanaa_university()
    seed_tofan_curriculum()
    seed_global_curricula()


if __name__ == "__main__":
    init_db()
