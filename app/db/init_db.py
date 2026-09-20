"""Create the initial database schema.

Migrations will replace this bootstrap helper as the project matures.
"""

from .base import Base
from .models import (  # noqa: F401
    AcademicPeriod,
    AcademicUnit,
    AuditLog,
    BiometricCredentialRecord,
    ContentFile,
    Course,
    Entitlement,
    Institution,
    Lecture,
    Unit,
    User,
    UserCredential,
    AuthSession,
    OtpChallenge,
)
from .session import engine
from app.auth.models import UserRole  # noqa: F401


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
