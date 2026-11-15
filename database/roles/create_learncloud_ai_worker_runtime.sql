-- Create/reconcile the dedicated K5 database login with the minimum privileges
-- required by ai_worker_service.py. This script contains no password.
-- Run as the database owner/admin while connected to database learncloud.
-- It never grants to or revokes from learncloud_video_runtime.

BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';
SET LOCAL search_path = pg_catalog, public;

DO $guard$
DECLARE
    missing_objects text;
    sequence_name text;
BEGIN
    IF current_database() <> 'learncloud' THEN
        RAISE EXCEPTION 'STOP: expected database learncloud, connected to %',
            current_database();
    END IF;

    SELECT string_agg(required.name, ', ' ORDER BY required.name)
    INTO missing_objects
    FROM (VALUES
        ('courses'), ('sections'), ('lessons'), ('video_uploads'),
        ('video_pipeline_runs'), ('quizzes'), ('questions'),
        ('flashcards'), ('quiz_attempts')
    ) AS required(name)
    WHERE to_regclass('public.' || required.name) IS NULL;

    IF missing_objects IS NOT NULL THEN
        RAISE EXCEPTION 'STOP: missing required K5 tables: %', missing_objects;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relname IN (
              'courses', 'sections', 'lessons', 'video_uploads',
              'video_pipeline_runs', 'quizzes', 'questions',
              'flashcards', 'quiz_attempts'
          )
          AND c.relrowsecurity
    ) THEN
        RAISE EXCEPTION 'STOP: RLS is enabled on a required table; review policies first';
    END IF;

    FOREACH sequence_name IN ARRAY ARRAY[
        pg_get_serial_sequence('public.quizzes', 'id'),
        pg_get_serial_sequence('public.questions', 'id'),
        pg_get_serial_sequence('public.flashcards', 'id')
    ]
    LOOP
        IF sequence_name IS NULL OR to_regclass(sequence_name) IS NULL THEN
            RAISE EXCEPTION 'STOP: a required K5 id sequence is missing';
        END IF;
    END LOOP;
END;
$guard$;

DO $create_role$
DECLARE
    runtime_role pg_roles%ROWTYPE;
BEGIN
    SELECT * INTO runtime_role
    FROM pg_roles
    WHERE rolname = 'learncloud_ai_worker_runtime';

    IF NOT FOUND THEN
        CREATE ROLE learncloud_ai_worker_runtime
            LOGIN
            NOSUPERUSER
            INHERIT
            NOCREATEDB
            NOCREATEROLE
            NOREPLICATION
            NOBYPASSRLS
            PASSWORD NULL;
    ELSIF (
        NOT runtime_role.rolcanlogin
        OR runtime_role.rolsuper
        OR runtime_role.rolcreatedb
        OR runtime_role.rolcreaterole
        OR runtime_role.rolreplication
        OR runtime_role.rolbypassrls
    ) THEN
        RAISE EXCEPTION
            'STOP: existing learncloud_ai_worker_runtime has incompatible role attributes';
    END IF;
END;
$create_role$;

DO $role_isolation$
DECLARE
    role_oid oid := (
        SELECT oid FROM pg_roles WHERE rolname = 'learncloud_ai_worker_runtime'
    );
BEGIN
    IF EXISTS (SELECT 1 FROM pg_auth_members WHERE member = role_oid) THEN
        RAISE EXCEPTION
            'STOP: learncloud_ai_worker_runtime inherits another role; review membership';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_database WHERE datdba = role_oid)
       OR EXISTS (SELECT 1 FROM pg_namespace WHERE nspowner = role_oid)
       OR EXISTS (
           SELECT 1 FROM pg_class
           WHERE relowner = role_oid AND relkind IN ('r', 'p', 'S', 'v', 'm', 'f')
       ) THEN
        RAISE EXCEPTION
            'STOP: learncloud_ai_worker_runtime owns database objects; review manually';
    END IF;
END;
$role_isolation$;

-- Reconcile only the dedicated K5 role. The transaction makes the revoke/grant
-- transition atomic. Privileges inherited through PUBLIC are checked below.
REVOKE ALL PRIVILEGES ON DATABASE learncloud
    FROM learncloud_ai_worker_runtime;
REVOKE ALL PRIVILEGES ON SCHEMA public
    FROM learncloud_ai_worker_runtime;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public
    FROM learncloud_ai_worker_runtime;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public
    FROM learncloud_ai_worker_runtime;

GRANT CONNECT ON DATABASE learncloud
    TO learncloud_ai_worker_runtime;
GRANT USAGE ON SCHEMA public
    TO learncloud_ai_worker_runtime;

-- Read the K4 ownership/identity ledger and the K5 content graph.
GRANT SELECT ON TABLE
    public.courses,
    public.sections,
    public.lessons,
    public.video_uploads,
    public.video_pipeline_runs,
    public.quizzes,
    public.questions,
    public.flashcards,
    public.quiz_attempts
TO learncloud_ai_worker_runtime;

-- SELECT FOR UPDATE requires UPDATE on at least one column. K5 never modifies
-- Course/Section data, so grant only their low-impact maintenance timestamp column;
-- primary/foreign keys and business content remain non-writable.
GRANT UPDATE (updated_at) ON TABLE public.courses
    TO learncloud_ai_worker_runtime;
GRANT UPDATE (update_at) ON TABLE public.sections
    TO learncloud_ai_worker_runtime;

-- Transcript, generated content and K5 state transitions. SQLAlchemy's onupdate
-- expression also writes updated_at whenever one of these entities is updated.
GRANT UPDATE (
    title,
    status,
    transcript_json,
    summary,
    key_concepts_json,
    error_message,
    updated_at
) ON TABLE public.lessons TO learncloud_ai_worker_runtime;

GRANT INSERT (
    section_id,
    title,
    passing_score,
    is_approved
) ON TABLE public.quizzes TO learncloud_ai_worker_runtime;
GRANT UPDATE (
    title,
    is_approved,
    updated_at
) ON TABLE public.quizzes TO learncloud_ai_worker_runtime;

-- K5 replaces generated questions and flashcards atomically; it does not update
-- existing rows and it never deletes a quiz or an attempt.
GRANT INSERT (
    quiz_id,
    question,
    options_json,
    correct_answer,
    explanation,
    topic,
    source_start_seconds,
    source_end_seconds,
    position
) ON TABLE public.questions TO learncloud_ai_worker_runtime;
GRANT DELETE ON TABLE public.questions
    TO learncloud_ai_worker_runtime;

GRANT INSERT (
    lesson_id,
    front,
    back,
    position,
    is_approved
) ON TABLE public.flashcards TO learncloud_ai_worker_runtime;
GRANT DELETE ON TABLE public.flashcards
    TO learncloud_ai_worker_runtime;

DO $grant_sequences$
DECLARE
    sequence_name text;
BEGIN
    FOREACH sequence_name IN ARRAY ARRAY[
        pg_get_serial_sequence('public.quizzes', 'id'),
        pg_get_serial_sequence('public.questions', 'id'),
        pg_get_serial_sequence('public.flashcards', 'id')
    ]
    LOOP
        EXECUTE format(
            'GRANT USAGE ON SEQUENCE %s TO learncloud_ai_worker_runtime',
            to_regclass(sequence_name)
        );
    END LOOP;
END;
$grant_sequences$;

-- Keep ORM resolution deterministic without changing any other database role.
ALTER ROLE learncloud_ai_worker_runtime IN DATABASE learncloud
    SET search_path = pg_catalog, public;

COMMIT;

