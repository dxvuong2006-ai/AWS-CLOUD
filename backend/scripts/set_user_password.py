import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.repositories.auth_repo import get_by_email
from app.services.auth_service import hash_password


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    password = getpass.getpass("New password (8-128 chars): ")
    confirm = getpass.getpass("Repeat password: ")
    if not (8 <= len(password) <= 128) or password != confirm:
        raise SystemExit("Password length invalid or passwords do not match")
    with SessionLocal() as db:
        user = get_by_email(db, args.email.strip().lower())
        if user is None:
            raise SystemExit("User not found")
        user.password_hash = hash_password(password)
        db.commit()
        print(f"Password updated for user id={user.id}, role={user.role}.")


if __name__ == "__main__":
    main()
