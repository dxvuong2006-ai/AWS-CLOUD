-- READ ONLY: verify the effective PostgreSQL privileges of the dedicated K5 role.
-- Run in pgAdmin against database learncloud after the GRANT script.

BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL lock_timeout = '3s';
SET LOCAL statement_timeout = '30s';
SET LOCAL search_path = pg_catalog, public;

DO $guard$
BEGIN
    IF current_database() <> 'learncloud' THEN
        RAISE EXCEPTION 'STOP: expected database learncloud, connected to %',
            current_database();
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles
        WHERE rolname = 'learncloud_ai_worker_runtime'
    ) THEN
        RAISE EXCEPTION 'STOP: role learncloud_ai_worker_runtime does not exist';
    END IF;
END;
$guard$;

SELECT
    rolname,
    rolcanlogin,
    rolsuper,
    rolcreatedb,
    rolcreaterole,
    rolreplication,
    rolbypassrls
FROM pg_roles
WHERE rolname = 'learncloud_ai_worker_runtime';

SELECT
    required.table_name,
    has_table_privilege(
        'learncloud_ai_worker_runtime',
        'public.' || required.table_name,
        'SELECT'
    ) AS can_select,
    has_any_column_privilege(
        'learncloud_ai_worker_runtime',
        'public.' || required.table_name,
        'INSERT'
    ) AS can_insert_any_column,
    has_any_column_privilege(
        'learncloud_ai_worker_runtime',
        'public.' || required.table_name,
        'UPDATE'
    ) AS can_update_any_column,
    has_table_privilege(
        'learncloud_ai_worker_runtime',
        'public.' || required.table_name,
        'DELETE'
    ) AS can_delete
FROM (VALUES
    ('courses'), ('sections'), ('lessons'), ('video_uploads'),
    ('video_pipeline_runs'), ('quizzes'), ('questions'),
    ('flashcards'), ('quiz_attempts')
) AS required(table_name)
ORDER BY required.table_name;

SELECT
    c.table_name,
    c.column_name,
    has_column_privilege(
        'learncloud_ai_worker_runtime',
        format('public.%I', c.table_name),
        c.column_name,
        'INSERT'
    ) AS can_insert,
    has_column_privilege(
        'learncloud_ai_worker_runtime',
        format('public.%I', c.table_name),
        c.column_name,
        'UPDATE'
    ) AS can_update
FROM information_schema.columns c
WHERE c.table_schema = 'public'
  AND c.table_name IN (
      'courses', 'sections', 'lessons', 'video_uploads',
      'video_pipeline_runs', 'quizzes', 'questions',
      'flashcards', 'quiz_attempts'
  )
  AND (
      has_column_privilege(
          'learncloud_ai_worker_runtime',
          format('public.%I', c.table_name),
          c.column_name,
          'INSERT'
      )
      OR has_column_privilege(
          'learncloud_ai_worker_runtime',
          format('public.%I', c.table_name),
          c.column_name,
          'UPDATE'
      )
  )
ORDER BY c.table_name, c.ordinal_position;

SELECT
    sequence_name,
    has_sequence_privilege(
        'learncloud_ai_worker_runtime', sequence_name, 'USAGE'
    ) AS can_use,
    has_sequence_privilege(
        'learncloud_ai_worker_runtime', sequence_name, 'SELECT'
    ) AS can_select_sequence,
    has_sequence_privilege(
        'learncloud_ai_worker_runtime', sequence_name, 'UPDATE'
    ) AS can_update_sequence
FROM unnest(ARRAY[
    pg_get_serial_sequence('public.quizzes', 'id'),
    pg_get_serial_sequence('public.questions', 'id'),
    pg_get_serial_sequence('public.flashcards', 'id')
]) AS sequence_name;

DO $verify$
DECLARE
    unexpected text;
BEGIN
    IF NOT has_database_privilege(
        'learncloud_ai_worker_runtime', 'learncloud', 'CONNECT'
    ) OR NOT has_schema_privilege(
        'learncloud_ai_worker_runtime', 'public', 'USAGE'
    ) OR has_schema_privilege(
        'learncloud_ai_worker_runtime', 'public', 'CREATE'
    ) THEN
        RAISE EXCEPTION 'STOP: database/schema privileges are not minimal';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_roles
        WHERE rolname = 'learncloud_ai_worker_runtime'
          AND (
              NOT rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
              OR rolreplication OR rolbypassrls
          )
    ) OR EXISTS (
        SELECT 1
        FROM pg_auth_members m
        JOIN pg_roles r ON r.oid = m.member
        WHERE r.rolname = 'learncloud_ai_worker_runtime'
    ) THEN
        RAISE EXCEPTION 'STOP: role attributes or memberships are not isolated';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM (VALUES
            ('courses'), ('sections'), ('lessons'), ('video_uploads'),
            ('video_pipeline_runs'), ('quizzes'), ('questions'),
            ('flashcards'), ('quiz_attempts')
        ) AS required(table_name)
        WHERE NOT has_table_privilege(
            'learncloud_ai_worker_runtime',
            'public.' || required.table_name,
            'SELECT'
        )
    ) THEN
        RAISE EXCEPTION 'STOP: required SELECT privilege is missing';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM (VALUES
            ('courses', 'updated_at', 'UPDATE'),
            ('sections', 'update_at', 'UPDATE'),
            ('lessons', 'title', 'UPDATE'),
            ('lessons', 'status', 'UPDATE'),
            ('lessons', 'transcript_json', 'UPDATE'),
            ('lessons', 'summary', 'UPDATE'),
            ('lessons', 'key_concepts_json', 'UPDATE'),
            ('lessons', 'error_message', 'UPDATE'),
            ('lessons', 'updated_at', 'UPDATE'),
            ('quizzes', 'section_id', 'INSERT'),
            ('quizzes', 'title', 'INSERT'),
            ('quizzes', 'passing_score', 'INSERT'),
            ('quizzes', 'is_approved', 'INSERT'),
            ('quizzes', 'title', 'UPDATE'),
            ('quizzes', 'is_approved', 'UPDATE'),
            ('quizzes', 'updated_at', 'UPDATE'),
            ('questions', 'quiz_id', 'INSERT'),
            ('questions', 'question', 'INSERT'),
            ('questions', 'options_json', 'INSERT'),
            ('questions', 'correct_answer', 'INSERT'),
            ('questions', 'explanation', 'INSERT'),
            ('questions', 'topic', 'INSERT'),
            ('questions', 'source_start_seconds', 'INSERT'),
            ('questions', 'source_end_seconds', 'INSERT'),
            ('questions', 'position', 'INSERT'),
            ('flashcards', 'lesson_id', 'INSERT'),
            ('flashcards', 'front', 'INSERT'),
            ('flashcards', 'back', 'INSERT'),
            ('flashcards', 'position', 'INSERT'),
            ('flashcards', 'is_approved', 'INSERT')
        ) AS required(table_name, column_name, privilege_name)
        WHERE NOT has_column_privilege(
            'learncloud_ai_worker_runtime',
            'public.' || required.table_name,
            required.column_name,
            required.privilege_name
        )
    ) THEN
        RAISE EXCEPTION 'STOP: a required column privilege is missing';
    END IF;

    IF NOT has_table_privilege(
        'learncloud_ai_worker_runtime', 'public.questions', 'DELETE'
    ) OR NOT has_table_privilege(
        'learncloud_ai_worker_runtime', 'public.flashcards', 'DELETE'
    ) THEN
        RAISE EXCEPTION 'STOP: required replace-content DELETE privilege is missing';
    END IF;

    -- Reject any effective INSERT/UPDATE column not listed above.
    SELECT string_agg(
        c.table_name || '.' || c.column_name || ':' || p.privilege_name,
        ', ' ORDER BY c.table_name, c.ordinal_position, p.privilege_name
    ) INTO unexpected
    FROM information_schema.columns c
    CROSS JOIN (VALUES ('INSERT'), ('UPDATE')) AS p(privilege_name)
    WHERE c.table_schema = 'public'
      AND has_column_privilege(
          'learncloud_ai_worker_runtime',
          format('public.%I', c.table_name),
          c.column_name,
          p.privilege_name
      )
      AND NOT EXISTS (
          SELECT 1
          FROM (VALUES
              ('courses', 'updated_at', 'UPDATE'),
              ('sections', 'update_at', 'UPDATE'),
              ('lessons', 'title', 'UPDATE'),
              ('lessons', 'status', 'UPDATE'),
              ('lessons', 'transcript_json', 'UPDATE'),
              ('lessons', 'summary', 'UPDATE'),
              ('lessons', 'key_concepts_json', 'UPDATE'),
              ('lessons', 'error_message', 'UPDATE'),
              ('lessons', 'updated_at', 'UPDATE'),
              ('quizzes', 'section_id', 'INSERT'),
              ('quizzes', 'title', 'INSERT'),
              ('quizzes', 'passing_score', 'INSERT'),
              ('quizzes', 'is_approved', 'INSERT'),
              ('quizzes', 'title', 'UPDATE'),
              ('quizzes', 'is_approved', 'UPDATE'),
              ('quizzes', 'updated_at', 'UPDATE'),
              ('questions', 'quiz_id', 'INSERT'),
              ('questions', 'question', 'INSERT'),
              ('questions', 'options_json', 'INSERT'),
              ('questions', 'correct_answer', 'INSERT'),
              ('questions', 'explanation', 'INSERT'),
              ('questions', 'topic', 'INSERT'),
              ('questions', 'source_start_seconds', 'INSERT'),
              ('questions', 'source_end_seconds', 'INSERT'),
              ('questions', 'position', 'INSERT'),
              ('flashcards', 'lesson_id', 'INSERT'),
              ('flashcards', 'front', 'INSERT'),
              ('flashcards', 'back', 'INSERT'),
              ('flashcards', 'position', 'INSERT'),
              ('flashcards', 'is_approved', 'INSERT')
          ) AS allowed(table_name, column_name, privilege_name)
          WHERE allowed.table_name = c.table_name
            AND allowed.column_name = c.column_name
            AND allowed.privilege_name = p.privilege_name
      );
    IF unexpected IS NOT NULL THEN
        RAISE EXCEPTION 'STOP: unexpected INSERT/UPDATE privileges: %', unexpected;
    END IF;

    SELECT string_agg(c.relname || ':' || p.privilege_name, ', ')
    INTO unexpected
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    CROSS JOIN (VALUES
        ('DELETE'), ('TRUNCATE'), ('REFERENCES'), ('TRIGGER')
    ) AS p(privilege_name)
    WHERE n.nspname = 'public'
      AND c.relkind IN ('r', 'p')
      AND has_table_privilege(
          'learncloud_ai_worker_runtime', c.oid, p.privilege_name
      )
      AND NOT (
          p.privilege_name = 'DELETE'
          AND c.relname IN ('questions', 'flashcards')
      );
    IF unexpected IS NOT NULL THEN
        RAISE EXCEPTION 'STOP: unexpected table privileges: %', unexpected;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM unnest(ARRAY[
            pg_get_serial_sequence('public.quizzes', 'id'),
            pg_get_serial_sequence('public.questions', 'id'),
            pg_get_serial_sequence('public.flashcards', 'id')
        ]) AS sequence_name
        WHERE sequence_name IS NULL
           OR NOT has_sequence_privilege(
               'learncloud_ai_worker_runtime', sequence_name, 'USAGE'
           )
           OR has_sequence_privilege(
               'learncloud_ai_worker_runtime', sequence_name, 'SELECT'
           )
           OR has_sequence_privilege(
               'learncloud_ai_worker_runtime', sequence_name, 'UPDATE'
           )
    ) THEN
        RAISE EXCEPTION 'STOP: sequence privileges are missing or too broad';
    END IF;
END;
$verify$;

SELECT 'PASS: learncloud_ai_worker_runtime privileges are exact' AS result;
COMMIT;
