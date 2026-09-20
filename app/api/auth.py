"""Authentication API routes for TOFAN Smart Academy."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.auth.authentication import AuthenticationError, login_email, register_email
from app.auth.sessions import get_session_user_id, revoke_session

router=APIRouter(prefix="/auth",tags=["auth"])

def get_db():
    db=SessionLocal()
    try: yield db
    finally: db.close()

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str|None=None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    device_id: str|None=None

class SessionResponse(BaseModel):
    access_token: str
    token_type: str="Bearer"

@router.post("/register",response_model=SessionResponse)
def register(payload:RegisterRequest,db:Session=Depends(get_db)):
    try:
        user=register_email(db,str(payload.email),payload.password,payload.display_name)
        from app.auth.sessions import create_session
        return SessionResponse(access_token=create_session(db,user.id))
    except (AuthenticationError,ValueError) as exc:
        raise HTTPException(status_code=400,detail=str(exc)) from exc

@router.post("/login",response_model=SessionResponse)
def login(payload:LoginRequest,db:Session=Depends(get_db)):
    try:
        return SessionResponse(access_token=login_email(db,str(payload.email),payload.password,payload.device_id))
    except AuthenticationError as exc:
        raise HTTPException(status_code=401,detail=str(exc)) from exc

@router.post("/logout")
def logout(token:str,db:Session=Depends(get_db)):
    revoke_session(db,token)
    return {"ok":True}

@router.get("/session")
def session(token:str,db:Session=Depends(get_db)):
    user_id=get_session_user_id(db,token)
    if user_id is None: raise HTTPException(status_code=401,detail="Invalid or expired session.")
    return {"authenticated":True,"user_id":user_id}
