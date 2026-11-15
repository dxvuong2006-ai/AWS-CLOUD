"""Apply the TutorSession reconciliation migration and query its ORM model on PostgreSQL.

This test uses a uniquely named temporary schema in the isolated P0.6 test DB;
it never resets or modifies the database's public schema.
"""

import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.models.tutor import TutorSession


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = (
    ROOT / "database/migrations/0012_reconcile_tutor_remediation_columns.sql"
).read_text(encoding="utf-8")
LIVE = os.environ.get("LEARNCLOUD_RUN_TUTOR_PG_TESTS") == "1"


def isolated_url(value: str):
    url = make_url(value)
    if (
        url.drivername not in {"postgresql", "postgresql+psycopg2"}
        or url.host not in {"127.0.0.1", "localhost", "::1"}
        or url.port != 55432
        or url.database != "learncloud_p06_test"
        or url.username != "learncloud_p06_test"
        or not set(url.query).issubset({"connect_timeout", "application_name"})
    ):
        raise RuntimeError("Only the isolated local learncloud_p06_test database is permitted")
    return url


@pytest.mark.skipif(not LIVE, reason="Set LEARNCLOUD_RUN_TUTOR_PG_TESTS=1 for isolated PostgreSQL")
def test_tutor_session_migration_and_orm_query_on_postgresql():
    url = isolated_url(os.environ["LEARNCLOUD_P06_TEST_DATABASE_URL"])
    engine = create_engine(url, hide_parameters=True, pool_pre_ping=True)
    schema = f"tutor_migration_test_{uuid4().hex}"
    quoted_schema = f'"{schema}"'
    try:
        with engine.connect() as connection:
            server_version = int(connection.scalar(text("SHOW server_version_num")))
            assert 160000 <= server_version < 170000

            connection.exec_driver_sql(f"CREATE SCHEMA {quoted_schema}")
            connection.commit()
            connection.exec_driver_sql(f"SET search_path TO {quoted_schema}")
            connection.exec_driver_sql(
                """
                CREATE TABLE schema_migrations (
                    version VARCHAR(50) PRIMARY KEY,
                    description TEXT NOT NULL,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE TABLE tutor_sessions (
                    id SERIAL PRIMARY KEY,
                    student_id INTEGER NOT NULL,
                    lesson_id INTEGER NOT NULL,
                    attempt_id INTEGER,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                INSERT INTO tutor_sessions(student_id, lesson_id, attempt_id)
                VALUES (17, 23, 8);
                """
            )
            connection.commit()

            raw = connection.connection.driver_connection
            with raw.cursor() as cursor:
                cursor.execute(MIGRATION)
            connection.commit()

            with Session(bind=connection) as db:
                row = db.scalars(select(TutorSession)).one()
                assert row.student_id == 17
                assert row.lesson_id == 23
                assert row.attempt_id == 8
                assert row.practice_questions == []
                assert row.remediation_completed is False
                assert row.workflow_state is None

            assert connection.scalar(
                text("SELECT version FROM schema_migrations WHERE version = '0012'")
            ) == "0012"
            connection.commit()
            connection.exec_driver_sql(f"DROP SCHEMA {quoted_schema} CASCADE")
            connection.commit()
    finally:
        with engine.connect() as connection:
            connection.rollback()
            connection.exec_driver_sql(f"DROP SCHEMA IF EXISTS {quoted_schema} CASCADE")
            connection.commit()
        engine.dispose()
