"""Authentication API routes for TOFAN Smart Academy."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.auth.authentication import AuthenticationError, ensure_owner_identity, login_email, register_email
from app.auth.biometric import BiometricAuthError
from app.auth.webauthn import begin_authentication, finish_authentication
from app.db.identity_models import StudentProfile, ProfileStatus
from app.db.models import User
from sqlalchemy import select
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


class PasskeyLoginOptionsRequest(BaseModel):
    email: EmailStr

class PasskeyLoginCompleteRequest(BaseModel):
    email: EmailStr
    challenge_id: str
    response: dict

@router.post("/passkey/options")
def passkey_login_options(payload: PasskeyLoginOptionsRequest, db: Session = Depends(get_db)):
    email = str(payload.email).strip().lower()
    user = db.scalar(select(User).where(User.email == email, User.is_active.is_(True)))
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid account or passkey.")
    try:
        result = begin_authentication(db, user)
        db.commit()
        return result
    except BiometricAuthError as exc:
        db.rollback()
        raise HTTPException(status_code=401, detail="No usable passkey is registered for this account.") from exc

@router.post("/passkey/complete", response_model=SessionResponse)
def passkey_login_complete(payload: PasskeyLoginCompleteRequest, db: Session = Depends(get_db)):
    email = str(payload.email).strip().lower()
    user = db.scalar(select(User).where(User.email == email, User.is_active.is_(True)))
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid account or passkey.")
    try:
        finish_authentication(db, user, payload.challenge_id, payload.response)
        ensure_owner_identity(db, user)
        profile = db.scalar(select(StudentProfile).where(StudentProfile.user_id == user.id))
        if profile is not None:
            profile.biometric_verified = True
            profile.profile_status = ProfileStatus.VERIFIED
        token = create_session(db, user.id, None)
        db.commit()
        return SessionResponse(access_token=token)
    except BiometricAuthError as exc:
        db.rollback()
        raise HTTPException(status_code=401, detail="Passkey verification failed.") from exc

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
