"""Grant the OWNER role to an existing academy account.

Usage:
    python scripts/bootstrap_owner.py owner@example.com
"""

import sys

from app.auth.bootstrap import grant_owner_by_email
from app.db.session import SessionLocal


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/bootstrap_owner.py owner@example.com")

    db = SessionLocal()
    try:
        user = grant_owner_by_email(db, sys.argv[1])
        print(f"OWNER role granted to: {user.email}")
        print(f"User ID: {user.id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
