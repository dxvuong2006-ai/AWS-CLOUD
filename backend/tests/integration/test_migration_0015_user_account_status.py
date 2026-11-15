"""Isolated PostgreSQL coverage for migration 0015; never uses app/RDS URLs."""

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = (ROOT / "database/migrations/0015_user_account_status.sql").read_text(
    encoding="utf-8"
)
PREFLIGHT = (ROOT / "database/checks/account_status_0015_preflight.sql").read_text(
    encoding="utf-8"
)
POSTFLIGHT = (ROOT / "database/checks/account_status_0015_postflight.sql").read_text(
    encoding="utf-8"
)
RUN = os.environ.get("LEARNCLOUD_RUN_0015_PG_TESTS") == "1"


def isolated_url(value: str):
    url = make_url(value)
    if (
        url.drivername not in {"postgresql", "postgresql+psycopg2"}
        or url.host not in {"127.0.0.1", "localhost", "::1"}
        or url.port != 55435
        or url.database != "learncloud_0015_test"
        or url.username != "learncloud_0015_test"
        or not set(url.query).issubset({"connect_timeout", "application_name"})
    ):
        raise RuntimeError(
            "Only local isolated PostgreSQL database learncloud_0015_test is permitted"
        )
    return url


def execute_script(engine, source: str):
    raw = engine.raw_connection()
    try:
        with raw.cursor() as cursor:
            cursor.execute(source)
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()


@pytest.mark.skipif(not RUN, reason="Set LEARNCLOUD_RUN_0015_PG_TESTS=1 for isolated PostgreSQL 16+")
def test_0015_adds_active_status_preserves_accounts_and_grants_only_runtime_status_access():
    url = isolated_url(os.environ["LEARNCLOUD_0015_TEST_DATABASE_URL"])
    engine = create_engine(url, hide_parameters=True, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT current_database()")) == "learncloud_0015_test"
            assert int(connection.scalar(text("SHOW server_version_num"))) >= 160000
            assert connection.scalar(text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user"))
            assert connection.scalar(text("""
                SELECT count(*) FROM pg_catalog.pg_roles
                WHERE rolname IN (
                    'learncloud_admin', 'learncloud_video_runtime',
                    'learncloud_ai_worker_runtime'
                )
            """)) == 0
            connection.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE")
            connection.exec_driver_sql("CREATE SCHEMA public AUTHORIZATION learncloud_0015_test")
            connection.commit()

        execute_script(engine, """
            CREATE ROLE learncloud_admin LOGIN;
            CREATE ROLE learncloud_video_runtime NOLOGIN;
            CREATE ROLE learncloud_ai_worker_runtime NOLOGIN;
            CREATE TABLE public.schema_migrations (
                version VARCHAR(50) PRIMARY KEY,
                description TEXT NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE TABLE public.users (
                id SERIAL PRIMARY KEY,
                cognito_sub VARCHAR(255) UNIQUE,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(320) NOT NULL UNIQUE,
                role VARCHAR(20) NOT NULL DEFAULT 'STUDENT'
                    CHECK (role IN ('STUDENT', 'INSTRUCTOR', 'ADMIN')),
                password_hash VARCHAR(255),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            INSERT INTO public.schema_migrations(version, description)
            VALUES ('0014', 'Secure lesson progress duration trigger permissions');
            INSERT INTO public.users(id, cognito_sub, name, email, role, password_hash)
            VALUES (101, 'sub-101', 'Existing Admin', 'admin@test.local', 'ADMIN', 'hash-a'),
                   (102, NULL, 'Existing Student', 'student@test.local', 'STUDENT', 'hash-b');
            GRANT USAGE ON SCHEMA public TO learncloud_admin;
            GRANT SELECT (id, cognito_sub, name, email, role, password_hash, created_at)
                ON public.users TO learncloud_admin;
            GRANT UPDATE (name, email, role) ON public.users TO learncloud_admin;
        """)
        execute_script(engine, PREFLIGHT)

        with engine.connect() as connection:
            before = connection.execute(text("""
                SELECT id, cognito_sub, name, email, role, password_hash
                FROM public.users ORDER BY id
            """)).all()

        execute_script(engine, MIGRATION)
        execute_script(engine, POSTFLIGHT)

        with engine.connect() as connection:
            after = connection.execute(text("""
                SELECT id, cognito_sub, name, email, role, password_hash
                FROM public.users ORDER BY id
            """)).all()
            statuses = connection.execute(text(
                "SELECT status FROM public.users ORDER BY id"
            )).scalars().all()
            assert after == before
            assert statuses == ["ACTIVE", "ACTIVE"]
            assert connection.scalar(text("""
                SELECT pg_catalog.has_column_privilege(
                    'learncloud_admin', 'public.users', 'status', 'SELECT'
                ) AND pg_catalog.has_column_privilege(
                    'learncloud_admin', 'public.users', 'status', 'UPDATE'
                )
            """)) is True
            for worker_role in ("learncloud_video_runtime", "learncloud_ai_worker_runtime"):
                assert connection.scalar(text("""
                    SELECT NOT pg_catalog.has_column_privilege(
                        :role, 'public.users', 'status', 'SELECT'
                    ) AND NOT pg_catalog.has_column_privilege(
                        :role, 'public.users', 'status', 'UPDATE'
                    )
                """), {"role": worker_role}) is True
            assert connection.scalar(text("""
                SELECT column_default = '''ACTIVE''::character varying'
                       AND is_nullable = 'NO'
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name='users' AND column_name='status'
            """)) is True
            assert connection.scalar(text("""
                SELECT count(*) FROM public.schema_migrations WHERE version='0015'
            """)) == 1

        # The next login uses the column default; the migration did not invent
        # or update any existing account state beyond marking it ACTIVE.
        with engine.begin() as connection:
            inserted = connection.scalar(text("""
                INSERT INTO public.users(name, email, role)
                VALUES ('New User', 'new@test.local', 'STUDENT') RETURNING status
            """))
            assert inserted == "ACTIVE"
            connection.execute(text("DELETE FROM public.users WHERE email='new@test.local'"))

        with pytest.raises(Exception) as replay_error:
            execute_script(engine, MIGRATION)
        assert getattr(replay_error.value, "pgcode", None) == "P0001"
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM public.users")) == 2
            connection.rollback()

        with engine.connect() as connection:
            with pytest.raises(Exception) as invalid_status:
                connection.execute(text("UPDATE public.users SET status='DISABLED' WHERE id=101"))
                connection.commit()
            assert getattr(invalid_status.value.orig, "pgcode", None) == "23514"
            connection.rollback()
    finally:
        with engine.connect() as connection:
            connection.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE")
            connection.exec_driver_sql(
                "CREATE SCHEMA public AUTHORIZATION learncloud_0015_test"
            )
            connection.commit()
        with engine.begin() as connection:
            connection.exec_driver_sql("DROP ROLE IF EXISTS learncloud_admin")
            connection.exec_driver_sql("DROP ROLE IF EXISTS learncloud_video_runtime")
            connection.exec_driver_sql("DROP ROLE IF EXISTS learncloud_ai_worker_runtime")
        engine.dispose()
