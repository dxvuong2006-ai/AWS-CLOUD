-- Run with SET ROLE to the existing trusted trigger-function owner after
-- reviewing the preflight. The Lambda runtime can update
-- lessons.duration_seconds, but cannot access lesson_progress directly.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';
SET LOCAL search_path = pg_catalog, public;

DO $preflight$
DECLARE
    trigger_function_oid oid;
    trigger_function_owner name;
    trigger_owner_is_superuser boolean;
BEGIN
    IF pg_catalog.to_regclass('public.lessons') IS NULL
       OR pg_catalog.to_regclass('public.lesson_progress') IS NULL
       OR pg_catalog.to_regclass('public.schema_migrations') IS NULL THEN
        RAISE EXCEPTION 'Lessons, lesson_progress, or schema_migrations is missing';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.schema_migrations
        WHERE version = '0014'
          AND description <> 'Secure lesson progress duration trigger permissions'
    ) THEN
        RAISE EXCEPTION 'Migration version 0014 is already used by another change';
    END IF;
    IF EXISTS (SELECT 1 FROM public.schema_migrations WHERE version = '0014') THEN
        RAISE EXCEPTION 'Migration 0014 is already registered; do not apply it again';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_attribute
        WHERE attrelid = 'public.lessons'::pg_catalog.regclass
          AND attname = 'duration_seconds' AND NOT attisdropped
          AND atttypid = 'pg_catalog.int4'::pg_catalog.regtype
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_attribute
        WHERE attrelid = 'public.lesson_progress'::pg_catalog.regclass
          AND attname = 'lesson_id' AND NOT attisdropped
          AND atttypid = 'pg_catalog.int4'::pg_catalog.regtype
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_attribute
        WHERE attrelid = 'public.lesson_progress'::pg_catalog.regclass
          AND attname = 'watched_seconds' AND NOT attisdropped
          AND atttypid = 'pg_catalog.int4'::pg_catalog.regtype
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_attribute
        WHERE attrelid = 'public.lesson_progress'::pg_catalog.regclass
          AND attname = 'completed' AND NOT attisdropped
          AND atttypid = 'pg_catalog.bool'::pg_catalog.regtype
          AND attnotnull
    ) THEN
        RAISE EXCEPTION 'Progress completion columns do not match the reviewed schema';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_class
        WHERE oid = 'public.lesson_progress'::pg_catalog.regclass
          AND (relrowsecurity OR relforcerowsecurity)
    ) THEN
        RAISE EXCEPTION 'lesson_progress has row-level security; review trigger policies first';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
        WHERE rolname = 'learncloud_video_runtime'
    ) THEN
        RAISE EXCEPTION 'Expected Lambda database role learncloud_video_runtime is missing';
    END IF;
    IF pg_catalog.has_any_column_privilege(
           'learncloud_video_runtime', 'public.lesson_progress', 'SELECT'
       ) OR pg_catalog.has_any_column_privilege(
           'learncloud_video_runtime', 'public.lesson_progress', 'INSERT'
       ) OR pg_catalog.has_any_column_privilege(
           'learncloud_video_runtime', 'public.lesson_progress', 'UPDATE'
       ) OR pg_catalog.has_table_privilege(
           'learncloud_video_runtime', 'public.lesson_progress', 'DELETE'
       ) OR pg_catalog.has_table_privilege(
           'learncloud_video_runtime', 'public.lesson_progress', 'TRUNCATE'
       ) OR pg_catalog.has_table_privilege(
           'learncloud_video_runtime', 'public.lesson_progress', 'REFERENCES'
       ) OR pg_catalog.has_table_privilege(
           'learncloud_video_runtime', 'public.lesson_progress', 'TRIGGER'
       ) THEN
        RAISE EXCEPTION 'Lambda runtime already has direct lesson_progress privileges; inspect grants';
    END IF;
    IF NOT pg_catalog.has_column_privilege(
        'learncloud_video_runtime', 'public.lessons', 'duration_seconds', 'UPDATE'
    ) THEN
        RAISE EXCEPTION 'Lambda runtime cannot update lessons.duration_seconds';
    END IF;

    SELECT procedure.oid, owner_role.rolname, owner_role.rolsuper
    INTO trigger_function_oid, trigger_function_owner, trigger_owner_is_superuser
    FROM pg_catalog.pg_proc AS procedure
    JOIN pg_catalog.pg_roles AS owner_role ON owner_role.oid = procedure.proowner
    WHERE procedure.pronamespace = 'public'::pg_catalog.regnamespace
      AND procedure.proname = 'sync_lesson_progress_completion_on_duration_change'
      AND procedure.pronargs = 0
      AND procedure.prorettype = 'pg_catalog.trigger'::pg_catalog.regtype;

    IF trigger_function_oid IS NULL OR NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_trigger AS trigger_row
        WHERE trigger_row.tgrelid = 'public.lessons'::pg_catalog.regclass
          AND trigger_row.tgname = 'trg_sync_lesson_progress_completion_on_duration_change'
          AND trigger_row.tgfoid = trigger_function_oid
          AND NOT trigger_row.tgisinternal
    ) THEN
        RAISE EXCEPTION 'Expected 0013 duration-completion trigger is missing or differs';
    END IF;
    IF trigger_function_owner = 'learncloud_video_runtime' THEN
        RAISE EXCEPTION 'Trigger function must not be owned by the Lambda runtime role';
    END IF;
    IF current_user <> trigger_function_owner THEN
        RAISE EXCEPTION 'Run migration as the existing trigger-function owner';
    END IF;
    IF NOT pg_catalog.has_schema_privilege(current_user, 'public', 'CREATE') THEN
        RAISE EXCEPTION 'Existing function owner needs CREATE on schema public to harden function body';
    END IF;
    IF trigger_owner_is_superuser THEN
        RAISE EXCEPTION 'Trigger function owner must not be a superuser';
    END IF;
    IF NOT pg_catalog.has_column_privilege(
           trigger_function_owner, 'public.lesson_progress', 'lesson_id', 'SELECT'
       ) OR NOT pg_catalog.has_column_privilege(
           trigger_function_owner, 'public.lesson_progress', 'watched_seconds', 'SELECT'
       ) OR NOT pg_catalog.has_column_privilege(
           trigger_function_owner, 'public.lesson_progress', 'completed', 'SELECT'
       ) OR NOT pg_catalog.has_column_privilege(
           trigger_function_owner, 'public.lesson_progress', 'completed', 'UPDATE'
       ) THEN
        RAISE EXCEPTION 'Existing function owner lacks required lesson_progress privileges';
    END IF;
END;
$preflight$;

-- Keep the existing trusted owner. Creating and transferring to a new role
-- would add an awkward PostgreSQL 16 creator membership and complicate safe
-- ownership transfer on managed PostgreSQL services.

CREATE OR REPLACE FUNCTION public.sync_lesson_progress_completion_on_duration_change()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $function$
BEGIN
    IF NEW.duration_seconds IS DISTINCT FROM OLD.duration_seconds THEN
        UPDATE public.lesson_progress AS progress
        SET completed = COALESCE(
            NEW.duration_seconds IS NOT NULL
            AND NEW.duration_seconds > 0
            AND progress.watched_seconds::pg_catalog.numeric >= NEW.duration_seconds::pg_catalog.numeric * 0.1,
            FALSE
        )
        WHERE progress.lesson_id = NEW.id
          AND progress.completed IS DISTINCT FROM COALESCE(
              NEW.duration_seconds IS NOT NULL
              AND NEW.duration_seconds > 0
              AND progress.watched_seconds::pg_catalog.numeric >= NEW.duration_seconds::pg_catalog.numeric * 0.1,
              FALSE
          );
    END IF;
    RETURN NEW;
END;
$function$;

REVOKE ALL ON FUNCTION public.sync_lesson_progress_completion_on_duration_change()
    FROM PUBLIC;
REVOKE ALL ON FUNCTION public.sync_lesson_progress_completion_on_duration_change()
    FROM learncloud_video_runtime;

DO $verify$
DECLARE
    function_oid oid := 'public.sync_lesson_progress_completion_on_duration_change()'::pg_catalog.regprocedure;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_proc AS procedure
        JOIN pg_catalog.pg_roles AS owner_role ON owner_role.oid = procedure.proowner
        WHERE procedure.oid = function_oid
          AND procedure.prosecdef
          AND owner_role.rolname = current_user
          AND NOT owner_role.rolsuper
          AND procedure.proconfig @> ARRAY['search_path=pg_catalog, pg_temp']
    ) THEN
        RAISE EXCEPTION 'Trigger function owner, SECURITY DEFINER, or search_path verification failed';
    END IF;

    IF NOT pg_catalog.has_column_privilege(
           current_user, 'public.lesson_progress', 'lesson_id', 'SELECT'
       ) OR NOT pg_catalog.has_column_privilege(
           current_user, 'public.lesson_progress', 'watched_seconds', 'SELECT'
       ) OR NOT pg_catalog.has_column_privilege(
           current_user, 'public.lesson_progress', 'completed', 'SELECT'
       ) OR NOT pg_catalog.has_column_privilege(
           current_user, 'public.lesson_progress', 'completed', 'UPDATE'
       ) THEN
        RAISE EXCEPTION 'Existing definer role no longer has privileges required by trigger';
    END IF;

    IF pg_catalog.has_any_column_privilege(
           'learncloud_video_runtime', 'public.lesson_progress', 'SELECT'
       ) OR pg_catalog.has_any_column_privilege(
           'learncloud_video_runtime', 'public.lesson_progress', 'INSERT'
       ) OR pg_catalog.has_any_column_privilege(
           'learncloud_video_runtime', 'public.lesson_progress', 'UPDATE'
       ) OR pg_catalog.has_table_privilege(
           'learncloud_video_runtime', 'public.lesson_progress', 'DELETE'
       ) OR pg_catalog.has_table_privilege(
           'learncloud_video_runtime', 'public.lesson_progress', 'TRUNCATE'
       ) OR pg_catalog.has_table_privilege(
           'learncloud_video_runtime', 'public.lesson_progress', 'REFERENCES'
       ) OR pg_catalog.has_table_privilege(
           'learncloud_video_runtime', 'public.lesson_progress', 'TRIGGER'
       ) THEN
        RAISE EXCEPTION 'Lambda runtime has direct lesson_progress access';
    END IF;
END;
$verify$;

INSERT INTO public.schema_migrations(version, description)
VALUES ('0014', 'Secure lesson progress duration trigger permissions');

COMMIT;
