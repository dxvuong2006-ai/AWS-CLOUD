"""PostgreSQL-only tests for the forward reconciliation of conflicting 0004 migrations."""

import os
from pathlib import Path

import pytest
from psycopg2 import Error as PsycopgError
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


ROOT = Path(__file__).resolve().parents[3]
SCHEMA_SQL = (ROOT / "database/schema.sql").read_text(encoding="utf-8")
MIGRATION_SQL = (
    ROOT / "database/migrations/0010_reconcile_0004_consistency.sql"
).read_text(encoding="utf-8")
HISTORICAL = ROOT / "database/migrations"
LIVE = os.environ.get("LEARNCLOUD_RUN_P06_DB_TESTS") == "1"


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
        raise RuntimeError("Only the isolated local P0.6 PostgreSQL database is permitted")
    return url


def execute_script(engine, source: str) -> None:
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


@pytest.fixture(scope="module")
def pg_engine():
    if not LIVE:
        pytest.skip("Set LEARNCLOUD_RUN_P06_DB_TESTS=1 for isolated PostgreSQL")
    url = isolated_url(os.environ["LEARNCLOUD_P06_TEST_DATABASE_URL"])
    engine = create_engine(url, hide_parameters=True, pool_pre_ping=True)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_database()")) == "learncloud_p06_test"
        version = int(connection.scalar(text("SHOW server_version_num")))
        assert 160000 <= version < 170000
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_schema(pg_engine):
    with pg_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.exec_driver_sql("DROP SCHEMA public CASCADE")
        connection.exec_driver_sql("CREATE SCHEMA public AUTHORIZATION learncloud_p06_test")
    execute_script(pg_engine, SCHEMA_SQL)


def seed_preserved_rows(engine) -> None:
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            INSERT INTO users(id,cognito_sub,name,email,role,password_hash)
            VALUES (101,'sub-101','Owner','owner-101@test.local','INSTRUCTOR','keep-hash'),
                   (102,NULL,'Student','student-102@test.local','STUDENT','keep-student-hash');
            INSERT INTO courses(id,instructor_id,title,status) VALUES (201,101,'P0.6','DRAFT');
            INSERT INTO sections(id,course_id,title,position) VALUES (301,201,'Section',1);
            INSERT INTO lessons(id,section_id,title,position,status)
            VALUES (401,301,'Lesson',1,'REVIEW_REQUIRED');
            INSERT INTO quizzes(id,section_id,title,is_approved)
            VALUES (501,301,'Checkpoint',FALSE);
            INSERT INTO quiz_attempts(id,student_id,quiz_id,score,passed,attempt_number)
            VALUES (601,102,501,40,FALSE,1);
            """
        )


def prepare_history(engine, state: str) -> None:
    seed_preserved_rows(engine)
    if state == "baseline":
        return
    if state == "legacy_v2":
        execute_script(
            engine,
            (HISTORICAL / "V2__allow_approved_lesson_status.sql").read_text(
                encoding="utf-8"
            ),
        )
        with engine.begin() as connection:
            connection.exec_driver_sql("UPDATE lessons SET status='APPROVED' WHERE id=401")
        return
    migration_name = {
        "approved": "0004_add_lesson_approved_status.sql",
        "checkpoint": "0004_checkpoint_attempt_idempotency.sql",
        "cognito": "0004_cognito_auth_cutover.sql",
        "canonical": "0004_remove_approved_lesson_status.sql",
    }[state]
    if state == "cognito":
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE users ALTER COLUMN password_hash SET NOT NULL"
            )
    execute_script(engine, (HISTORICAL / migration_name).read_text(encoding="utf-8"))
    if state == "approved":
        with engine.begin() as connection:
            connection.exec_driver_sql("UPDATE lessons SET status='APPROVED' WHERE id=401")


def assert_canonical(engine, expected_0004: str | None) -> None:
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT password_hash FROM users WHERE id=101")) == "keep-hash"
        assert connection.scalar(text("SELECT count(*) FROM quiz_attempts WHERE id=601")) == 1
        assert connection.scalar(text("SELECT count(*) FROM checkpoint_remediation")) == 0
        assert connection.scalar(text("SELECT count(*) FROM schema_migrations WHERE version='0010'")) == 1
        assert connection.scalar(text("SELECT description FROM schema_migrations WHERE version='0004'")) == expected_0004
        assert connection.scalar(text("SELECT is_nullable FROM information_schema.columns WHERE table_schema='public' AND table_name='users' AND column_name='password_hash'")) == "YES"
        assert connection.scalar(text("SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND table_name='quiz_attempts' AND column_name IN ('request_id','request_hash')")) == 2
        constraint = connection.scalar(text("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='public.lessons'::regclass AND conname='ck_lessons_status'"))
        assert "APPROVED" not in constraint
        assert connection.scalar(text("SELECT status FROM lessons WHERE id=401")) in {"REVIEW_REQUIRED", "PUBLISHED"}


@pytest.mark.parametrize(
    ("state", "description"),
    [
        ("baseline", None),
        ("legacy_v2", None),
        ("approved", "Allow APPROVED Lesson status for explicit review before course publishing"),
        ("checkpoint", "checkpoint idempotency and mandatory remediation"),
        ("cognito", "Prepare user identity mapping for Cognito authentication"),
        ("canonical", "Remove approved lesson status; publish directly after review"),
    ],
)
def test_reconciles_historical_0004_states_and_preserves_registry(
    pg_engine, state, description,
):
    prepare_history(pg_engine, state)
    execute_script(pg_engine, MIGRATION_SQL)
    assert_canonical(pg_engine, description)


def test_repeat_is_idempotent_and_preserves_data(pg_engine):
    prepare_history(pg_engine, "approved")
    execute_script(pg_engine, MIGRATION_SQL)
    execute_script(pg_engine, MIGRATION_SQL)
    assert_canonical(
        pg_engine,
        "Allow APPROVED Lesson status for explicit review before course publishing",
    )
    with pg_engine.connect() as connection:
        assert connection.scalar(text("SELECT status FROM lessons WHERE id=401")) == "PUBLISHED"


def test_historical_runner_reproduces_0004_collision_and_0005_block(pg_engine):
    """The documented filename/version runner selects add-approved and skips the rest."""
    files = sorted(HISTORICAL.glob("0004_*.sql"), key=lambda item: item.name)
    for migration in files:
        with pg_engine.connect() as connection:
            applied = connection.scalar(
                text("SELECT 1 FROM schema_migrations WHERE version='0004'")
            )
        if not applied:
            execute_script(pg_engine, migration.read_text(encoding="utf-8"))

    with pg_engine.connect() as connection:
        assert connection.scalar(
            text("SELECT description FROM schema_migrations WHERE version='0004'")
        ) == "Allow APPROVED Lesson status for explicit review before course publishing"
        assert connection.scalar(text("SELECT to_regclass('public.checkpoint_remediation')")) is None
        assert connection.scalar(
            text("SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND table_name='quiz_attempts' AND column_name IN ('request_id','request_hash')")
        ) == 0

    with pytest.raises(PsycopgError):
        execute_script(
            pg_engine,
            (HISTORICAL / "0005_video_pipeline_ledger.sql").read_text(encoding="utf-8"),
        )
    with pg_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM schema_migrations WHERE version='0005'")) == 0
        assert connection.scalar(text("SELECT to_regclass('public.video_uploads')")) is None


def test_canonical_chain_plus_0010_has_current_backend_prerequisites(pg_engine):
    seed_preserved_rows(pg_engine)
    for migration_name in (
        "0003_reconcile_legacy_schema.sql",
        "0004_remove_approved_lesson_status.sql",
        "0005_video_pipeline_ledger.sql",
        "V3__add_tutor_remediation_fields.sql",
        "0006_screen_workflows.sql",
        "0007_dual_auth.sql",
        "0008_local_auth_provisioning.sql",
    ):
        execute_script(
            pg_engine,
            (HISTORICAL / migration_name).read_text(encoding="utf-8"),
        )
    execute_script(pg_engine, MIGRATION_SQL)

    with pg_engine.connect() as connection:
        assert set(
            connection.scalars(
                text("SELECT version FROM schema_migrations WHERE version BETWEEN '0003' AND '0010'")
            )
        ) == {"0003", "0004", "0005", "0006", "0007", "0008", "0010"}
        for relation in (
            "video_uploads", "video_pipeline_runs", "checkpoint_remediation",
            "local_auth_identities", "local_auth_otps", "local_auth_sessions",
        ):
            assert connection.scalar(
                text("SELECT to_regclass(:relation)"), {"relation": f"public.{relation}"},
            ) == relation
        assert connection.scalar(
            text("SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND table_name='tutor_sessions' AND column_name IN ('workflow_state','practice_questions','remediation_completed')")
        ) == 3
        assert connection.scalar(
            text("SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND table_name='local_auth_identities' AND column_name IN ('provisioned_at','provisioned_by','provisioning_reference')")
        ) == 3


def test_failure_rolls_back_all_changes(pg_engine):
    prepare_history(pg_engine, "approved")
    with pg_engine.begin() as connection:
        connection.exec_driver_sql("ALTER TABLE users ALTER COLUMN password_hash SET NOT NULL")
        connection.exec_driver_sql("CREATE TABLE checkpoint_remediation (attempt_id INTEGER PRIMARY KEY)")

    with pytest.raises(PsycopgError):
        execute_script(pg_engine, MIGRATION_SQL)

    with pg_engine.connect() as connection:
        assert connection.scalar(text("SELECT status FROM lessons WHERE id=401")) == "APPROVED"
        assert connection.scalar(text("SELECT is_nullable FROM information_schema.columns WHERE table_schema='public' AND table_name='users' AND column_name='password_hash'")) == "NO"
        assert connection.scalar(text("SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND table_name='quiz_attempts' AND column_name IN ('request_id','request_hash')")) == 0
        assert connection.scalar(text("SELECT count(*) FROM schema_migrations WHERE version='0010'")) == 0


@pytest.mark.parametrize(
    "value",
    [
        "postgresql://learncloud_p06_test@production.example.com:55432/learncloud_p06_test",
        "postgresql://learncloud_p06_test@127.0.0.1:5432/learncloud_p06_test",
        "postgresql://learncloud_p06_test@127.0.0.1:55432/learncloud",
        "postgresql://other@127.0.0.1:55432/learncloud_p06_test",
    ],
)
def test_guard_refuses_non_isolated_targets(value):
    with pytest.raises(RuntimeError):
        isolated_url(value)
