"""Core account authentication and identity-linking flows."""
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.models import User,UserCredential
from app.auth.models import RoleName, UserRole
import os
from .passwords import hash_password,verify_password
from .providers import AuthProvider,VerifiedIdentity
from .sessions import create_session
class AuthenticationError(ValueError): pass

OWNER_EMAIL = os.getenv("TOFAN_OWNER_EMAIL", "raedtofan86@gmail.com").strip().lower()

def ensure_owner_identity(db: Session, user: User) -> User:
    if not user.email or user.email.strip().lower() != OWNER_EMAIL:
        return user
    role = db.scalar(select(UserRole).where(UserRole.user_id == user.id, UserRole.role == RoleName.OWNER))
    if role is None:
        db.add(UserRole(user_id=user.id, role=RoleName.OWNER, is_active=True))
        db.commit()
    elif not role.is_active:
        role.is_active = True
        db.commit()
    return user
def find_or_create_identity(db: Session,identity: VerifiedIdentity)->User:
    c=db.scalar(select(UserCredential).where(UserCredential.provider==identity.provider.value,UserCredential.provider_subject==identity.subject))
    if c:
        u=db.get(User,c.user_id)
        if u is None or not u.is_active: raise AuthenticationError("Account is unavailable.")
        return u
    u=db.scalar(select(User).where(User.email==identity.email)) if identity.email else None
    if u is None and identity.phone: u=db.scalar(select(User).where(User.phone==identity.phone))
    if u is None: u=User(email=identity.email,phone=identity.phone,display_name=identity.display_name); db.add(u); db.flush()
    db.add(UserCredential(user_id=u.id,provider=identity.provider.value,provider_subject=identity.subject)); db.commit(); return u
def register_email(db: Session,email: str,password: str,display_name: str|None=None)->User:
    email=email.strip().lower()
    if db.scalar(select(User).where(User.email==email)): raise AuthenticationError("Email is already registered.")
    u=User(email=email,display_name=display_name); db.add(u); db.flush()
    db.add(UserCredential(user_id=u.id,provider=AuthProvider.EMAIL.value,provider_subject=email,secret_hash=hash_password(password))); db.commit(); return ensure_owner_identity(db, u)
def login_email(db: Session,email: str,password: str,device_id: str|None=None)->str:
    email=email.strip().lower(); c=db.scalar(select(UserCredential).where(UserCredential.provider==AuthProvider.EMAIL.value,UserCredential.provider_subject==email))
    if c is None or not c.secret_hash or not verify_password(password,c.secret_hash): raise AuthenticationError("Invalid email or password.")
    u=db.get(User,c.user_id)
    if u is None or not u.is_active: raise AuthenticationError("Account is unavailable.")
    ensure_owner_identity(db, u)
    return create_session(db,u.id,device_id)
