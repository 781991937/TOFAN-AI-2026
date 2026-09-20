"""Database engine/session configuration."""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./tofan.db",
)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
