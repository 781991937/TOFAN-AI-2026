"""One-time password challenge storage."""
import hashlib, hmac, os, secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.models import OtpChallenge
OTP_PEPPER=os.getenv("AUTH_OTP_PEPPER","")
def _digest(challenge_id: str, code: str) -> str:
    if not OTP_PEPPER: raise RuntimeError("AUTH_OTP_PEPPER is required for OTP authentication.")
    return hmac.new(OTP_PEPPER.encode(),(challenge_id+":"+code).encode(),hashlib.sha256).hexdigest()
def create_otp(db: Session,user_id: str|None,destination: str,minutes: int=5)->tuple[str,str]:
    c=OtpChallenge(user_id=user_id,destination=destination,code_hash="pending",expires_at=datetime.now(timezone.utc)+timedelta(minutes=minutes))
    db.add(c); db.flush(); code=f"{secrets.randbelow(1000000):06d}"; c.code_hash=_digest(c.id,code); db.commit(); return c.id,code
def consume_otp(db: Session,challenge_id: str,code: str,max_attempts: int=5)->OtpChallenge|None:
    c=db.scalar(select(OtpChallenge).where(OtpChallenge.id==challenge_id))
    if c is None or c.consumed_at is not None or c.expires_at<=datetime.now(timezone.utc) or c.attempts>=max_attempts: return None
    c.attempts+=1
    if hmac.compare_digest(c.code_hash,_digest(c.id,code)): c.consumed_at=datetime.now(timezone.utc); db.commit(); return c
    db.commit(); return None
