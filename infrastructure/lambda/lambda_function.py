"""One-off read-only AWS Lambda -> Amazon RDS PostgreSQL connection probe.

Requires pg8000 and the official RDS regional CA bundle packaged in the ZIP.
No SSM tunnel, EC2 bastion, or external internet is necessary at invocation.
"""
import os
import ssl
import time
from pathlib import Path

import pg8000.dbapi


def lambda_handler(event, context):
    started = time.monotonic()
    needed = ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD")
    missing = [name for name in needed if not os.environ.get(name)]
    if missing:
        return {"ok": False, "error": "Missing environment variables", "names": missing}

    ca_path = Path(__file__).with_name("ap-southeast-1-bundle.pem")
    if not ca_path.is_file():
        return {"ok": False, "error": "RDS CA bundle missing from Lambda ZIP"}

    connection = None
    try:
        tls = ssl.create_default_context(cafile=str(ca_path))
        # Hostname and certificate chain are verified against the AWS RDS CA.
        connection = pg8000.dbapi.connect(
            host=os.environ["DB_HOST"],
            port=int(os.environ.get("DB_PORT", "5432")),
            database=os.environ["DB_NAME"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            ssl_context=tls,
            timeout=8,
            application_name="learncloud-lambda-rds-probe",
        )
        cur = connection.cursor()
        cur.execute("""
            SELECT current_database(), current_user,
                   (SELECT count(*) FROM public.courses),
                   (SELECT count(*) FROM public.lessons),
                   (SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid())
        """)
        database, username, courses, lessons, tls_enabled = cur.fetchone()
        cur.close()
        return {
            "ok": True,
            "database": database,
            "user": username,
            "courses": courses,
            "lessons": lessons,
            "tls_enabled": tls_enabled,
            "duration_ms": round((time.monotonic() - started) * 1000),
        }
    except Exception as exc:
        # Do not log or return DB credentials, connection URLs, or event contents.
        print("RDS probe failed:", type(exc).__name__)
        return {"ok": False, "error_type": type(exc).__name__, "error": "Inspect connectivity, credentials, role grants and TLS CA"}
    finally:
        if connection is not None:
            connection.close()
