"""Authentication foundation tests."""
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.auth.models import RoleName, UserRole
from app.auth.authentication import login_email, register_email
from app.auth.passwords import hash_password, verify_password
from app.db.base import Base
from app.db.models import User
import app.db.models  # noqa: F401
import app.auth.models  # noqa: F401


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_password_hashing():
    encoded = hash_password("correct horse battery")
    assert encoded != "correct horse battery"
    assert verify_password("correct horse battery", encoded)
    assert not verify_password("wrong password", encoded)


def test_email_registration_and_login():
    db = make_db()
    user = register_email(db, "student@example.com", "correct horse battery", "Student")
    assert user.email == "student@example.com"
    token = login_email(db, "student@example.com", "correct horse battery", "android-1")
    assert token


def test_configured_owner_email_receives_owner_role(monkeypatch):
    monkeypatch.setenv("TOFAN_OWNER_EMAIL", "owner@example.com")

    # authentication.py reads the configured owner email at import time, so
    # exercise the production default contract with its configured address.
    from app.auth import authentication

    monkeypatch.setattr(authentication, "OWNER_EMAIL", "owner@example.com")

    db = make_db()
    user = register_email(db, "OWNER@EXAMPLE.COM", "correct horse battery", "Owner")

    role = db.scalar(
        select(UserRole).where(
            UserRole.user_id == user.id,
            UserRole.role == RoleName.OWNER,
        )
    )
    assert role is not None
    assert role.is_active is True

    token = login_email(db, "owner@example.com", "correct horse battery", "owner-device")
    assert token


def test_non_owner_email_does_not_receive_owner_role():
    db = make_db()
    user = register_email(db, "student@example.com", "correct horse battery", "Student")

    role = db.scalar(
        select(UserRole).where(
            UserRole.user_id == user.id,
            UserRole.role == RoleName.OWNER,
        )
    )
    assert role is None
