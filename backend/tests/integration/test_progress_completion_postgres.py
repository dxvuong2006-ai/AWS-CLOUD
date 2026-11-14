"""PostgreSQL integration test for persisted completion reconciliation."""

import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.models.progress import LessonProgress


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = (
    ROOT / "database/migrations/0013_sync_progress_completion_on_duration_change.sql"
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
def test_backfilled_duration_reconciles_and_tracks_persisted_progress_on_postgresql():
    url = isolated_url(os.environ["LEARNCLOUD_P06_TEST_DATABASE_URL"])
    engine = create_engine(url, hide_parameters=True, pool_pre_ping=True)
    schema = f"progress_completion_test_{uuid4().hex}"
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
                CREATE TABLE lessons (
                    id INTEGER PRIMARY KEY,
                    duration_seconds INTEGER
                );
                CREATE TABLE lesson_progress (
                    id SERIAL PRIMARY KEY,
                    student_id INTEGER NOT NULL,
                    lesson_id INTEGER NOT NULL,
                    watched_seconds INTEGER NOT NULL DEFAULT 0,
                    last_position_seconds DOUBLE PRECISION NOT NULL DEFAULT 0,
                    watched_ranges JSONB NOT NULL DEFAULT '[]'::jsonb,
                    completed BOOLEAN NOT NULL DEFAULT FALSE,
                    playback_session_id VARCHAR(36),
                    last_sequence INTEGER NOT NULL DEFAULT 0,
                    last_request_id VARCHAR(36),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                INSERT INTO lessons(id, duration_seconds)
                VALUES (24, 119), (25, NULL), (26, 0);
                INSERT INTO lesson_progress(student_id, lesson_id, watched_seconds, completed)
                VALUES (17, 24, 118, FALSE), (17, 25, 118, FALSE), (17, 26, 118, TRUE);
                """
            )
            connection.commit()

            raw = connection.connection.driver_connection
            with raw.cursor() as cursor:
                cursor.execute(MIGRATION)
            connection.commit()

            with Session(bind=connection) as db:
                rows = {
                    row.lesson_id: row.completed
                    for row in db.scalars(
                        select(LessonProgress).where(LessonProgress.student_id == 17)
                    )
                }
                assert rows == {24: True, 25: False, 26: False}

            # A later duration backfill uses the trigger and persists completion.
            connection.exec_driver_sql(
                "UPDATE lessons SET duration_seconds = 119 WHERE id = 25"
            )
            connection.commit()
            with Session(bind=connection) as db:
                progress = db.scalar(
                    select(LessonProgress).where(
                        LessonProgress.student_id == 17,
                        LessonProgress.lesson_id == 25,
                    )
                )
                assert progress.completed is True

            assert connection.scalar(
                text("SELECT version FROM schema_migrations WHERE version = '0013'")
            ) == "0013"
            connection.commit()
    finally:
        with engine.connect() as connection:
            connection.rollback()
            connection.exec_driver_sql(f"DROP SCHEMA IF EXISTS {quoted_schema} CASCADE")
            connection.commit()
        engine.dispose()
