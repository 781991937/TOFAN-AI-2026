"""Authentication foundation tests."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
import app.db.models  # noqa: F401
import app.auth.models  # noqa: F401
from app.auth.authentication import login_email, register_email
from app.auth.passwords import hash_password, verify_password

def make_db():
    engine=create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()

def test_password_hashing():
    encoded=hash_password("correct horse battery")
    assert encoded != "correct horse battery"
    assert verify_password("correct horse battery",encoded)
    assert not verify_password("wrong password",encoded)

def test_email_registration_and_login():
    db=make_db()
    user=register_email(db,"student@example.com","correct horse battery","Student")
    assert user.email=="student@example.com"
    token=login_email(db,"student@example.com","correct horse battery","android-1")
    assert token
