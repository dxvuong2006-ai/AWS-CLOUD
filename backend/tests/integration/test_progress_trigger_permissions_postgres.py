"""PostgreSQL 16 integration coverage for migration 0014 trigger privileges.

Uses only a dedicated local test database. The test login is an isolated test
administrator; application writes run under learncloud_video_runtime via SET ROLE.
"""

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


ROOT = Path(__file__).resolve().parents[3]
MIGRATION_0013 = (
    ROOT / "database/migrations/0013_sync_progress_completion_on_duration_change.sql"
).read_text(encoding="utf-8")
MIGRATION_0014 = (
    ROOT / "database/migrations/0014_secure_progress_duration_trigger.sql"
).read_text(encoding="utf-8")
RUN = os.environ.get("LEARNCLOUD_RUN_0014_PG_TESTS") == "1"


def isolated_url(value: str):
    url = make_url(value)
    if (
        url.drivername not in {"postgresql", "postgresql+psycopg2"}
        or url.host not in {"127.0.0.1", "localhost", "::1"}
        or url.port != 55434
        or url.database != "learncloud_0014_test"
        or url.username != "learncloud_0014_test"
        or not set(url.query).issubset({"connect_timeout", "application_name"})
    ):
        raise RuntimeError("Only local isolated PostgreSQL database learncloud_0014_test is permitted")
    return url


def execute_script(engine, source: str, *, role: str | None = None) -> None:
    raw = engine.raw_connection()
    try:
        with raw.cursor() as cursor:
            if role is not None:
                cursor.execute(f'SET ROLE "{role}"')
            cursor.execute(source)
        raw.commit()
        if role is not None:
            with raw.cursor() as cursor:
                cursor.execute("RESET ROLE")
            raw.commit()
    except Exception:
        raw.rollback()
        if role is not None:
            with raw.cursor() as cursor:
                cursor.execute("RESET ROLE")
            raw.commit()
        raise
    finally:
        raw.close()


@pytest.mark.skipif(not RUN, reason="Set LEARNCLOUD_RUN_0014_PG_TESTS=1 for isolated PostgreSQL 16")
def test_0014_runtime_duration_update_syncs_progress_without_direct_progress_privileges():
    url = isolated_url(os.environ["LEARNCLOUD_0014_TEST_DATABASE_URL"])
    engine = create_engine(url, hide_parameters=True, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT current_database()")) == "learncloud_0014_test"
            assert 160000 <= int(connection.scalar(text("SHOW server_version_num"))) < 170000
            connection.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE")
            connection.exec_driver_sql("CREATE SCHEMA public AUTHORIZATION learncloud_0014_test")
            connection.commit()

        execute_script(engine, """
            CREATE TABLE public.schema_migrations (
                version VARCHAR(50) PRIMARY KEY,
                description TEXT NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE TABLE public.lessons (
                id INTEGER PRIMARY KEY,
                duration_seconds INTEGER
            );
            CREATE TABLE public.lesson_progress (
                id SERIAL PRIMARY KEY,
                student_id INTEGER NOT NULL,
                lesson_id INTEGER NOT NULL,
                watched_seconds INTEGER NOT NULL DEFAULT 0,
                completed BOOLEAN NOT NULL DEFAULT FALSE
            );
            DO $runtime_role$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles
                               WHERE rolname = 'learncloud_video_runtime') THEN
                    CREATE ROLE learncloud_video_runtime NOLOGIN;
                END IF;
            END;
            $runtime_role$;
            DO $admin_role$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles
                               WHERE rolname = 'learncloud_admin') THEN
                    CREATE ROLE learncloud_admin NOLOGIN CREATEROLE;
                END IF;
            END;
            $admin_role$;
            ALTER ROLE learncloud_admin NOLOGIN CREATEROLE NOSUPERUSER;
            GRANT USAGE ON SCHEMA public TO learncloud_admin;
            GRANT USAGE ON SCHEMA public TO learncloud_video_runtime;
            GRANT CREATE ON SCHEMA public TO learncloud_admin;
            GRANT SELECT, INSERT ON public.schema_migrations TO learncloud_admin;
            ALTER TABLE public.lesson_progress OWNER TO learncloud_admin;
            GRANT SELECT (id, duration_seconds), UPDATE (duration_seconds)
                ON public.lessons TO learncloud_video_runtime;
            INSERT INTO public.lessons(id, duration_seconds) VALUES (101, NULL), (102, 119);
            INSERT INTO public.lesson_progress(student_id, lesson_id, watched_seconds, completed)
            VALUES (17, 101, 118, FALSE), (18, 101, 5, FALSE), (19, 102, 118, FALSE);
        """)

        execute_script(engine, MIGRATION_0013)
        execute_script(engine, """
            ALTER FUNCTION public.sync_lesson_progress_completion_on_duration_change()
                OWNER TO learncloud_admin;
        """)
        # Reproduce the reported failure: the 0013 SECURITY INVOKER trigger
        # attempts UPDATE on lesson_progress using the restricted runtime role.
        with engine.connect() as connection:
            connection.exec_driver_sql("SET LOCAL ROLE learncloud_video_runtime")
            with pytest.raises(Exception) as old_trigger_error:
                connection.exec_driver_sql(
                    "UPDATE public.lessons SET duration_seconds = 119 WHERE id = 101"
                )
            assert getattr(old_trigger_error.value.orig, "pgcode", None) == "42501"
            connection.rollback()
        with engine.connect() as connection:
            assert connection.scalar(text(
                "SELECT duration_seconds FROM public.lessons WHERE id = 101"
            )) is None

        # The migration must fail closed when runtime has unexpected direct
        # progress access, without changing the function or registry.
        execute_script(
            engine,
            "GRANT SELECT ON public.lesson_progress TO learncloud_video_runtime",
        )
        with pytest.raises(Exception) as preflight_error:
            execute_script(engine, MIGRATION_0014, role="learncloud_admin")
        assert getattr(preflight_error.value, "pgcode", None) == "P0001", str(preflight_error.value)
        with engine.connect() as connection:
            assert connection.scalar(text("""
                SELECT count(*) FROM public.schema_migrations WHERE version = '0014'
            """)) == 0
            assert connection.scalar(text("""
                SELECT NOT procedure.prosecdef
                FROM pg_catalog.pg_proc AS procedure
                WHERE procedure.oid =
                    'public.sync_lesson_progress_completion_on_duration_change()'::regprocedure
            """)) is True
        execute_script(
            engine,
            "REVOKE SELECT ON public.lesson_progress FROM learncloud_video_runtime",
        )
        execute_script(engine, MIGRATION_0014, role="learncloud_admin")
        execute_script(engine, "REVOKE CREATE ON SCHEMA public FROM learncloud_admin")

        with engine.connect() as connection:
            metadata = connection.execute(text("""
                SELECT procedure.prosecdef, procedure.proconfig,
                       owner.rolname, owner.rolcanlogin, owner.rolsuper,
                       owner.rolcreatedb, owner.rolcreaterole, owner.rolinherit,
                       owner.rolreplication, owner.rolbypassrls,
                       pg_catalog.has_column_privilege(owner.rolname,
                           'public.lesson_progress', 'lesson_id', 'SELECT') AS lesson_id_select,
                       pg_catalog.has_column_privilege(owner.rolname,
                           'public.lesson_progress', 'watched_seconds', 'SELECT') AS watched_select,
                       pg_catalog.has_column_privilege(owner.rolname,
                           'public.lesson_progress', 'completed', 'SELECT') AS completed_select,
                       pg_catalog.has_column_privilege(owner.rolname,
                           'public.lesson_progress', 'completed', 'UPDATE') AS completed_update,
                       pg_catalog.has_function_privilege(
                            'learncloud_video_runtime',
                            'public.sync_lesson_progress_completion_on_duration_change()',
                            'EXECUTE') AS runtime_function_execute
                FROM pg_catalog.pg_proc AS procedure
                JOIN pg_catalog.pg_roles AS owner ON owner.oid = procedure.proowner
                WHERE procedure.oid =
                    'public.sync_lesson_progress_completion_on_duration_change()'::regprocedure
            """)).mappings().one()
            assert metadata["prosecdef"] is True
            assert metadata["proconfig"] == ["search_path=pg_catalog, pg_temp"]
            assert metadata["rolname"] == "learncloud_admin"
            assert metadata["rolcanlogin"] is False
            assert metadata["rolsuper"] is False
            assert metadata["rolcreaterole"] is True
            assert metadata["lesson_id_select"] is True
            assert metadata["watched_select"] is True
            assert metadata["completed_select"] is True
            assert metadata["completed_update"] is True
            assert metadata["runtime_function_execute"] is False
            assert connection.scalar(text("""
                SELECT count(*) FROM public.schema_migrations
                WHERE version IN ('0013', '0014')
            """)) == 2

            # Updating duration as the restricted Lambda role invokes the
            # SECURITY DEFINER trigger and updates progress for every learner.
            connection.exec_driver_sql("SET LOCAL ROLE learncloud_video_runtime")
            connection.exec_driver_sql(
                "UPDATE public.lessons SET duration_seconds = 119 WHERE id = 101"
            )
            connection.commit()

        with engine.connect() as connection:
            rows = connection.execute(text("""
                SELECT student_id, completed FROM public.lesson_progress
                WHERE lesson_id = 101 ORDER BY student_id
            """)).all()
            assert rows == [(17, True), (18, False)]
            assert connection.scalar(text("""
                SELECT completed FROM public.lesson_progress
                WHERE student_id = 19 AND lesson_id = 102
            """)) is True

        # The Lambda role still cannot read or write lesson_progress directly.
        for statement in (
            "SELECT completed FROM public.lesson_progress WHERE student_id = 17",
            "UPDATE public.lesson_progress SET completed = FALSE WHERE student_id = 17",
        ):
            with engine.connect() as connection:
                connection.exec_driver_sql("SET LOCAL ROLE learncloud_video_runtime")
                with pytest.raises(Exception) as caught:
                    connection.exec_driver_sql(statement)
                assert getattr(caught.value.orig, "pgcode", None) == "42501"
                connection.rollback()
    finally:
        # This database is dedicated to this test; leave it clean for a rerun.
        with engine.connect() as connection:
            connection.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE")
            connection.exec_driver_sql("CREATE SCHEMA public AUTHORIZATION learncloud_0014_test")
            connection.commit()
        engine.dispose()
