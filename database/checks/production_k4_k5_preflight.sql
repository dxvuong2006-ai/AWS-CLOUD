-- READ ONLY: production readiness gate for K4 + K5.
-- Run against database learncloud with the same DB role used by the Lambdas.
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL lock_timeout = '3s';
SET LOCAL statement_timeout = '30s';
SET LOCAL search_path = pg_catalog, public;

SELECT current_database() AS database,
       current_user AS application_role,
       current_setting('server_version') AS postgres_version,
       current_setting('transaction_read_only') AS transaction_read_only;

DO $guard$
DECLARE
    missing_tables text;
    missing_columns text;
BEGIN
    IF current_database() <> 'learncloud' THEN
        RAISE EXCEPTION 'STOP: expected production database learncloud';
    END IF;

    SELECT string_agg(required.name, ', ' ORDER BY required.name)
    INTO missing_tables
    FROM (VALUES
        ('schema_migrations'), ('users'), ('courses'), ('sections'), ('lessons'),
        ('quizzes'), ('questions'), ('flashcards'), ('video_uploads'),
        ('video_pipeline_runs')
    ) AS required(name)
    WHERE to_regclass('public.' || required.name) IS NULL;
    IF missing_tables IS NOT NULL THEN
        RAISE EXCEPTION 'STOP: missing required tables: %', missing_tables;
    END IF;

    SELECT string_agg(required.table_name || '.' || required.column_name, ', '
                      ORDER BY required.table_name, required.column_name)
    INTO missing_columns
    FROM (VALUES
        ('lessons','raw_video_key'), ('lessons','processed_video_key'),
        ('lessons','status'), ('lessons','transcript_json'), ('lessons','summary'),
        ('lessons','key_concepts_json'), ('lessons','retry_count'),
        ('lessons','error_message'), ('quizzes','section_id'),
        ('quizzes','is_approved'), ('questions','quiz_id'),
        ('questions','options_json'), ('questions','correct_answer'),
        ('flashcards','lesson_id'), ('flashcards','is_approved'),
        ('video_uploads','source_key'), ('video_uploads','size_bytes'),
        ('video_uploads','expires_at'), ('video_pipeline_runs','attempt'),
        ('video_pipeline_runs','state'), ('video_pipeline_runs','execution_arn'),
        ('video_pipeline_runs','source_etag'), ('video_pipeline_runs','output_key'),
        ('video_pipeline_runs','job_id'), ('video_pipeline_runs','safe_to_retry'),
        ('video_pipeline_runs','next_dispatch_at')
    ) AS required(table_name, column_name)
    WHERE NOT EXISTS (
        SELECT 1 FROM information_schema.columns c
        WHERE c.table_schema = 'public'
          AND c.table_name = required.table_name
          AND c.column_name = required.column_name
    );
    IF missing_columns IS NOT NULL THEN
        RAISE EXCEPTION 'STOP: missing required columns: %', missing_columns;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM public.schema_migrations
        WHERE version = '0005'
          AND description = 'Add video upload intents and pipeline ledger with upload/lesson integrity'
    ) THEN
        RAISE EXCEPTION 'STOP: migration 0005 registry entry is missing or incompatible';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.lessons
        WHERE status IS NULL OR status NOT IN (
            'DRAFT', 'UPLOADED', 'PROCESSING', 'TRANSCRIBING',
            'AI_PROCESSING', 'REVIEW_REQUIRED', 'APPROVED', 'PUBLISHED', 'FAILED'
        )
    ) THEN
        RAISE EXCEPTION 'STOP: unsupported Lesson status exists';
    END IF;

    IF (SELECT count(*) FROM pg_constraint
        WHERE conrelid IN ('public.video_uploads'::regclass,
                           'public.video_pipeline_runs'::regclass)
          AND convalidated
          AND conname IN (
              'uq_video_upload_id_lesson', 'ck_video_upload_size',
              'uq_video_run_upload_attempt', 'fk_video_run_upload_lesson',
              'ck_video_run_attempt', 'ck_video_run_state'
          )) <> 6 THEN
        RAISE EXCEPTION 'STOP: required 0005 constraints are missing or unvalidated';
    END IF;
END;
$guard$;

SELECT version, description, applied_at
FROM public.schema_migrations
WHERE version IN ('0004', '0005', '0009')
ORDER BY version;

SELECT status, count(*) AS lessons
FROM public.lessons
GROUP BY status
ORDER BY status;

SELECT count(*) AS legacy_approved_lessons
FROM public.lessons
WHERE status = 'APPROVED';

SELECT conname, convalidated, pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE conrelid = 'public.lessons'::regclass
  AND contype = 'c'
  AND conname IN ('lessons_status_check', 'ck_lessons_status', 'chk_lessons_status')
ORDER BY conname;

SELECT current_user AS role,
       has_table_privilege(current_user, 'public.lessons', 'SELECT,UPDATE') AS lessons_rw,
       has_table_privilege(current_user, 'public.sections', 'SELECT') AS sections_read,
       has_table_privilege(current_user, 'public.quizzes', 'SELECT,INSERT,UPDATE') AS quizzes_rw,
       has_table_privilege(current_user, 'public.questions', 'SELECT,INSERT,DELETE') AS questions_rw,
       has_table_privilege(current_user, 'public.flashcards', 'SELECT,INSERT,DELETE') AS flashcards_rw,
       has_table_privilege(current_user, 'public.video_uploads', 'SELECT,INSERT') AS uploads_rw,
       has_table_privilege(current_user, 'public.video_pipeline_runs', 'SELECT,INSERT,UPDATE') AS runs_rw;

DO $integrity$
DECLARE
    mismatch_count bigint;
BEGIN
    SELECT count(*) INTO mismatch_count
    FROM public.video_pipeline_runs r
    LEFT JOIN public.video_uploads u
      ON u.id = r.upload_id AND u.lesson_id = r.lesson_id
    WHERE u.id IS NULL;
    IF mismatch_count <> 0 THEN
        RAISE EXCEPTION 'STOP: % pipeline runs have missing/mismatched uploads', mismatch_count;
    END IF;
END;
$integrity$;

COMMIT;
