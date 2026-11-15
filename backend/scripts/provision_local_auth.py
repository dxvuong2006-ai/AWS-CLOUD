"""Interactive, dry-run-by-default provisioning of an exact existing user ID.

DBA authorization is a PostgreSQL role membership, never a client-supplied role.
Passwords are only accepted through a protected console prompt.
"""
import argparse
import getpass
import json
from pathlib import Path
import sys
import warnings

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--user-id", type=int, required=True)
    result.add_argument("--expected-email", required=True)
    result.add_argument("--expected-role", choices=["INSTRUCTOR", "ADMIN"], required=True)
    result.add_argument("--expected-cognito-sub", required=True, help="Exact subject, or NONE if SQL NULL")
    result.add_argument("--operator-db-user", required=True, help="Direct DB login authorized by the DBA")
    result.add_argument("--approval-reference", required=True)
    result.add_argument("--apply", action="store_true", help="Write only after console confirmation; default is read-only preview")
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    if args.user_id < 1:
        raise SystemExit("A positive exact user ID is required.")
    if not sys.stdin.isatty():
        raise SystemExit("A trusted interactive terminal is required; no piped passwords or echo fallback.")
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import Session
    from app.config import settings
    from app.services import local_auth_provisioning as provisioning
    from app.services import local_auth_service

    engine = None
    try:
        local_auth_service.require_enabled()
        url = make_url(settings.DATABASE_URL)
        if url.get_backend_name() != "postgresql":
            raise provisioning.ProvisioningError("Only PostgreSQL is supported.")
        # Keep configured host/port/database/TLS. Separate operator credentials
        # exist only in this connection, never in .env or process environment.
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            db_password = getpass.getpass("Authorized provisioning DB login password: ")
            url = url.set(username=args.operator_db_user, password=db_password)
            options = "-c search_path=public -c lock_timeout=5s -c statement_timeout=30s"
            if not args.apply:
                options += " -c default_transaction_read_only=on"
            engine = create_engine(url, hide_parameters=True, connect_args={
                "connect_timeout": 5, "application_name": "learncloud_local_auth_provisioning", "options": options})
            target = {"user_id": args.user_id, "expected_email": args.expected_email,
                      "expected_role": args.expected_role,
                      "expected_cognito_sub": None if args.expected_cognito_sub == "NONE" else args.expected_cognito_sub}
            with Session(engine, autoflush=False) as db:
                user, operator = provisioning.inspect_target(db, **target)
                if operator != args.operator_db_user:
                    raise provisioning.ProvisioningError("Authenticated DB login differs from the requested operator.")
                print(json.dumps({"mode": "apply" if args.apply else "read-only preview", "operator": operator,
                    "host": url.host, "port": url.port, "database": url.database,
                    "user_id": user.id, "email": user.email, "role": user.role, "cognito_sub": user.cognito_sub}, ensure_ascii=False))
                db.rollback()
                if not args.apply:
                    print("No data changed. Obtain approval before repeating with --apply.")
                    return 0
                if input(f"Type PROVISION {args.user_id} after verifying the person and approval: ") != f"PROVISION {args.user_id}":
                    raise provisioning.ProvisioningError("Confirmation did not match; nothing changed.")
                password = getpass.getpass("New local password (12-128 characters): ")
                confirmation = getpass.getpass("Repeat new local password: ")
                if password != confirmation:
                    raise provisioning.ProvisioningError("Passwords do not match; nothing changed.")
                with db.begin():
                    result = provisioning.provision(db, **target, password=password,
                                                    approval_reference=args.approval_reference)
                print(json.dumps({"status": "provisioned", **result}, ensure_ascii=False))
                return 0
    except (provisioning.ProvisioningError, local_auth_service.LocalAuthError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        # Database exceptions can carry DSNs/parameters; never print raw detail.
        print(f"Provisioning failed ({type(exc).__name__}); verify transaction outcome before retrying. Review schema/permissions securely.", file=sys.stderr)
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
