"""Authentication API routes for TOFAN Smart Academy."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.auth.authentication import AuthenticationError, login_email, register_email
from app.auth.dependencies import get_current_session, get_db
from app.auth.sessions import create_session, revoke_session

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str | None = None
    device_id: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    device_id: str | None = None


class SessionResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"


@router.post("/register", response_model=SessionResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    try:
        user = register_email(
            db, str(payload.email), payload.password, payload.display_name
        )
        return SessionResponse(
            access_token=create_session(db, user.id, payload.device_id)
        )
    except (AuthenticationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/login", response_model=SessionResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    try:
        return SessionResponse(
            access_token=login_email(
                db, str(payload.email), payload.password, payload.device_id
            )
        )
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/logout")
def logout(current=Depends(get_current_session), db: Session = Depends(get_db)):
    # Revoke the current session without accepting a token in the URL.
    from app.db.models import AuthSession

    session = db.get(AuthSession, current.id)
    if session is not None and session.revoked_at is None:
        from datetime import datetime

        session.revoked_at = datetime.utcnow()
        db.commit()
    return {"ok": True}


@router.get("/session")
def session(current=Depends(get_current_session)):
    return {"authenticated": True, "user_id": current.user_id}
