"""Authenticated user and session management API."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_roles, get_current_session, get_current_user, get_db
from app.auth.models import RoleName
from app.db.models import AuthSession, User

router = APIRouter(prefix="/users", tags=["users"])


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    display_name: str | None
    email: str | None
    phone: str | None
    is_active: bool
    created_at: datetime


class ProfileUpdateRequest(BaseModel):
    display_name: str | None = None


class RoleResponse(BaseModel):
    role: str


class SessionItemResponse(BaseModel):
    id: str
    device_id: str | None
    created_at: datetime
    last_seen_at: datetime | None
    expires_at: datetime
    revoked_at: datetime | None
    current: bool


@router.get("/me", response_model=ProfileResponse)
def me(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=ProfileResponse)
def update_me(
    payload: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user.display_name = payload.display_name.strip() if payload.display_name else None
    db.commit()
    db.refresh(user)
    return user


@router.get("/me/roles", response_model=list[RoleResponse])
def my_roles(roles: list[RoleName] = Depends(get_current_roles)):
    return [{"role": role.value} for role in roles]


@router.get("/me/sessions", response_model=list[SessionItemResponse])
def my_sessions(
    current=Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(AuthSession)
        .where(AuthSession.user_id == user.id)
        .order_by(AuthSession.created_at.desc())
    ).all()
    return [
        SessionItemResponse(
            id=row.id,
            device_id=row.device_id,
            created_at=row.created_at,
            last_seen_at=row.last_seen_at,
            expires_at=row.expires_at,
            revoked_at=row.revoked_at,
            current=row.id == current.id,
        )
        for row in rows
    ]


@router.delete("/me/sessions/{session_id}")
def revoke_my_session(
    session_id: str,
    current=Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.scalar(
        select(AuthSession).where(
            AuthSession.id == session_id,
            AuthSession.user_id == user.id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    if row.revoked_at is None:
        row.revoked_at = datetime.utcnow()
        db.commit()

    return {"ok": True, "current_session": row.id == current.id}


@router.delete("/me/sessions")
def revoke_all_other_sessions(
    current=Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    now = datetime.utcnow()
    rows = db.scalars(
        select(AuthSession).where(
            AuthSession.user_id == user.id,
            AuthSession.id != current.id,
            AuthSession.revoked_at.is_(None),
        )
    ).all()

    for row in rows:
        row.revoked_at = now

    db.commit()
    return {"ok": True, "revoked_count": len(rows)}
