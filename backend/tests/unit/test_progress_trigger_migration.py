from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_0014_is_transactional_and_uses_the_existing_trusted_owner():
    sql = (ROOT / "database/migrations/0014_secure_progress_duration_trigger.sql").read_text(
        encoding="utf-8"
    )
    normalized = "\n".join(
        line for line in sql.splitlines() if not line.lstrip().startswith("--")
    )

    assert normalized.index("BEGIN;") < normalized.index("CREATE OR REPLACE FUNCTION")
    assert normalized.index("INSERT INTO public.schema_migrations") < normalized.index("COMMIT;")
    assert "SECURITY DEFINER" in normalized
    assert "SET search_path = pg_catalog, pg_temp" in normalized
    assert "current_user" in normalized
    assert "CREATE ROLE" not in normalized
    assert "OWNER TO learncloud_progress_trigger_owner" not in normalized
    assert "GRANT UPDATE ON TABLE public.lesson_progress TO learncloud_video_runtime" not in normalized
    assert "GRANT SELECT ON TABLE public.lesson_progress TO learncloud_video_runtime" not in normalized
    assert "UPDATE public.lesson_progress AS progress" in normalized
    assert "public.lesson_progress" in normalized
    assert "public.lessons" in normalized
    assert "public.sync_lesson_progress_completion_on_duration_change()" in normalized
    assert "NEW.duration_seconds::pg_catalog.numeric * 0.1" in normalized
    assert "watched_seconds =" not in normalized
    assert "watched_ranges =" not in normalized


def test_0014_preflights_runtime_access_and_trigger_identity():
    sql = (ROOT / "database/migrations/0014_secure_progress_duration_trigger.sql").read_text(
        encoding="utf-8"
    )
    assert "has_any_column_privilege" in sql
    assert "learncloud_video_runtime" in sql
    assert "Expected 0013 duration-completion trigger is missing or differs" in sql
    assert "Run migration as the existing trigger-function owner" in sql
    assert "row-level security" in sql
    assert "VALUES ('0014', 'Secure lesson progress duration trigger permissions')" in sql
