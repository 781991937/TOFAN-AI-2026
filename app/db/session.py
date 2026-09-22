"""Database engine/session configuration for development and production."""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

_raw_url = os.getenv("DATABASE_URL", "sqlite:///./tofan.db")
DATABASE_URL = _raw_url
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgres://"):]
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgresql://"):]

if os.getenv("TOFAN_ENV", "development").lower() == "production" and DATABASE_URL.startswith("sqlite"):
    raise RuntimeError("Production requires DATABASE_URL to point to PostgreSQL.")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
pool_kwargs = {}
if not DATABASE_URL.startswith("sqlite"):
    pool_kwargs = {
        "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10")),
    }

engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args, **pool_kwargs)
SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
