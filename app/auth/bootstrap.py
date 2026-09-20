"""Controlled bootstrap helpers for the first academy owner."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import RoleName, UserRole
from app.db.models import User


def grant_role(db: Session, user: User, role: RoleName) -> UserRole:
    existing = db.scalar(
        select(UserRole).where(
            UserRole.user_id == user.id,
            UserRole.role == role,
        )
    )
    if existing is not None:
        existing.is_active = True
        db.commit()
        return existing

    assignment = UserRole(user_id=user.id, role=role, is_active=True)
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


def grant_owner_by_email(db: Session, email: str) -> User:
    normalized = email.strip().lower()
    user = db.scalar(select(User).where(User.email == normalized))
    if user is None:
        raise ValueError("No account exists for this email. Register the account first.")

    if not user.is_active:
        raise ValueError("The account is inactive.")

    grant_role(db, user, RoleName.OWNER)
    return user
