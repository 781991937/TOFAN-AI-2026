"""Opaque server-side authentication sessions."""
import hashlib, secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.models import AuthSession
def _hash_token(token: str) -> str: return hashlib.sha256(token.encode()).hexdigest()
def create_session(db: Session, user_id: str, device_id: str | None = None, days: int = 30) -> str:
    token=secrets.token_urlsafe(48); now=datetime.now(timezone.utc)
    db.add(AuthSession(user_id=user_id,token_hash=_hash_token(token),device_id=device_id,expires_at=now+timedelta(days=days),last_seen_at=now)); db.commit(); return token
def get_session_user_id(db: Session, token: str) -> str | None:
    row=db.scalar(select(AuthSession).where(AuthSession.token_hash==_hash_token(token)))
    if row is None or row.revoked_at is not None or row.expires_at <= datetime.now(timezone.utc): return None
    row.last_seen_at=datetime.now(timezone.utc); db.commit(); return row.user_id
def revoke_session(db: Session, token: str) -> None:
    row=db.scalar(select(AuthSession).where(AuthSession.token_hash==_hash_token(token)))
    if row is not None: row.revoked_at=datetime.now(timezone.utc); db.commit()
