"""FastAPI authentication dependencies."""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import RoleName, UserRole
from app.auth.sessions import get_session
from app.db.models import User
from app.db.session import SessionLocal

bearer_scheme = HTTPBearer(auto_error=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authentication required.")

    session = get_session(db, credentials.credentials)
    if session is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session.")

    return session


def get_current_user(
    session=Depends(get_current_session),
    db: Session = Depends(get_db),
) -> User:
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Account is unavailable.")
    return user


def get_current_roles(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RoleName]:
    rows = db.scalars(
        select(UserRole).where(
            UserRole.user_id == user.id,
            UserRole.is_active.is_(True),
        )
    ).all()
    return [row.role for row in rows]
