-- Read-only verification for the isolated LearnCloud K5 database.
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '30s';
SET LOCAL search_path = pg_catalog, public;

DO $guard$
DECLARE
    missing_tables TEXT;
    invalid_constraints INTEGER;
BEGIN
    IF current_database() <> 'learncloud_k5_test' THEN
        RAISE EXCEPTION 'Refusing database %, expected learncloud_k5_test', current_database();
    END IF;
    IF (
        SELECT pg_catalog.pg_get_userbyid(d.datdba)
        FROM pg_catalog.pg_database d
        WHERE d.datname = pg_catalog.current_database()
    ) <> 'learncloud_k5_test_user' THEN
        RAISE EXCEPTION 'Database owner must be learncloud_k5_test_user';
    END IF;

    SELECT pg_catalog.string_agg(required.name, ', ' ORDER BY required.name)
    INTO missing_tables
    FROM (VALUES
        ('users'), ('courses'), ('sections'), ('lessons'), ('flashcards'),
        ('enrollments'), ('lesson_progress'), ('quizzes'), ('questions'),
        ('quiz_attempts'), ('quiz_answers'), ('checkpoint_remediation'),
        ('tutor_sessions'), ('tutor_messages'), ('video_uploads'),
        ('video_pipeline_runs'), ('local_auth_identities'), ('local_auth_otps'),
        ('local_auth_sessions'), ('schema_migrations')
    ) AS required(name)
    WHERE pg_catalog.to_regclass('public.' || required.name) IS NULL;

    IF missing_tables IS NOT NULL THEN
        RAISE EXCEPTION 'Missing required tables: %', missing_tables;
    END IF;

    SELECT count(*) INTO invalid_constraints
    FROM pg_catalog.pg_constraint c
    JOIN pg_catalog.pg_namespace n ON n.oid = c.connamespace
    WHERE n.nspname = 'public' AND NOT c.convalidated;

    IF invalid_constraints <> 0 THEN
        RAISE EXCEPTION 'Found % unvalidated constraints', invalid_constraints;
    END IF;
END;
$guard$;

SELECT version, description
FROM public.schema_migrations
ORDER BY version;

SELECT c.relname AS table_name,
       count(*) FILTER (WHERE con.contype = 'f') AS foreign_keys,
       count(*) FILTER (WHERE con.contype = 'c') AS check_constraints,
       count(*) FILTER (WHERE con.contype IN ('p', 'u')) AS key_constraints
FROM pg_catalog.pg_class c
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
LEFT JOIN pg_catalog.pg_constraint con ON con.conrelid = c.oid
WHERE n.nspname = 'public' AND c.relkind = 'r'
GROUP BY c.relname
ORDER BY c.relname;

SELECT schemaname, tablename, indexname, indexdef
FROM pg_catalog.pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;

SELECT r.id AS run_id, r.state, r.attempt, l.status AS lesson_status,
       r.output_key = l.processed_video_key AS output_matches_lesson
FROM public.video_pipeline_runs r
JOIN public.lessons l ON l.id = r.lesson_id
WHERE r.id = 'cb1d51e7cf146c2547aab8ff4f11eba90718a6f9f4ae5d89198e03f47113977a';

ROLLBACK;
