"""Run idempotent TOFAN database migrations."""

from app.db.migrations import run_migrations
from app.db.session import engine


if __name__ == "__main__":
    changes = run_migrations(engine)
    if changes:
        print("Applied migrations:")
        for change in changes:
            print(f"- {change}")
    else:
        print("Database is already up to date.")
