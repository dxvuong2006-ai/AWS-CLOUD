-- READ ONLY: inspect before/after 0005. Never creates tables, records versions,
-- confirms uploads or changes application data. Use psql -X -v ON_ERROR_STOP=1.
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL lock_timeout = '3s';
SET LOCAL statement_timeout = '30s';
SET LOCAL search_path = pg_catalog, public;

SELECT current_database() AS database, current_user AS inspecting_role,
       current_setting('server_version') AS postgres_version,
       current_setting('transaction_read_only') AS transaction_read_only;

DO $baseline$
BEGIN
    IF to_regclass('public.schema_migrations') IS NULL
       OR to_regclass('public.lessons') IS NULL
       OR to_regclass('public.courses') IS NULL THEN
        RAISE EXCEPTION 'STOP: missing LearnCloud baseline tables';
    END IF;
END;
$baseline$;

SELECT version, description, applied_at FROM public.schema_migrations
WHERE version IN ('0004', '0005') ORDER BY version;
SELECT has_schema_privilege(current_user, 'public', 'CREATE') AS can_create_in_public,
       has_table_privilege(current_user, 'public.lessons', 'REFERENCES') AS can_reference_lessons,
       has_table_privilege(current_user, 'public.schema_migrations', 'INSERT') AS can_record_version;
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'lessons' AND column_name IN ('id', 'status', 'retry_count');
SELECT conname, convalidated, pg_get_constraintdef(oid) AS definition
FROM pg_constraint WHERE conrelid = 'public.lessons'::regclass AND contype = 'c'
ORDER BY conname;
SELECT status, count(*) AS lesson_count, count(processed_video_key) AS lessons_with_processed_key,
       sum(retry_count) AS total_retries
FROM public.lessons GROUP BY status ORDER BY status;
SELECT status, count(*) AS course_count FROM public.courses GROUP BY status ORDER BY status;

SELECT to_regclass('public.video_uploads') AS uploads_table,
       to_regclass('public.video_pipeline_runs') AS runs_table;
SELECT table_name, column_name, data_type, character_maximum_length, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name IN ('video_uploads', 'video_pipeline_runs')
ORDER BY table_name, ordinal_position;
SELECT conrelid::regclass AS table_name, conname, contype, convalidated,
       pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE conrelid IN (to_regclass('public.video_uploads'), to_regclass('public.video_pipeline_runs'))
ORDER BY table_name, conname;
SELECT tablename, indexname, indexdef FROM pg_indexes
WHERE schemaname = 'public' AND tablename IN ('video_uploads', 'video_pipeline_runs')
ORDER BY tablename, indexname;

DO $checks$
DECLARE
    uploads regclass := to_regclass('public.video_uploads');
    runs regclass := to_regclass('public.video_pipeline_runs');
    recorded_description text;
    mismatch_count bigint;
    upload_count bigint;
    run_count bigint;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM public.schema_migrations WHERE version = '0004'
          AND description = 'Remove approved lesson status; publish directly after review'
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conrelid = 'public.lessons'::regclass
          AND conname = 'ck_lessons_status' AND contype = 'c' AND convalidated
          AND pg_get_constraintdef(oid) NOT LIKE '%''APPROVED''%'
    ) THEN
        RAISE EXCEPTION 'STOP: 0004 registry/validated non-APPROVED constraint is missing or incompatible';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns WHERE table_schema = 'public'
          AND table_name = 'lessons' AND column_name = 'id' AND udt_name = 'int4'
    ) THEN
        RAISE EXCEPTION 'STOP: expected lessons.id INTEGER from the LearnCloud baseline';
    END IF;
    SELECT description INTO recorded_description FROM public.schema_migrations WHERE version = '0005';
    IF NOT FOUND THEN
        IF uploads IS NOT NULL OR runs IS NOT NULL THEN
            RAISE EXCEPTION 'STOP: unversioned/partial ledger tables exist; do not drop, recreate or auto-register them';
        END IF;
        RAISE NOTICE 'READY_TO_APPLY: 0004 validated; 0005 absent; both ledger tables absent. Review backup/permissions before manual apply.';
        RETURN;
    END IF;
    IF recorded_description IS DISTINCT FROM 'Add video upload intents and pipeline ledger with upload/lesson integrity' THEN
        RAISE EXCEPTION 'STOP: version 0005 belongs to another change';
    END IF;
    IF uploads IS NULL OR runs IS NULL THEN
        RAISE EXCEPTION 'STOP: 0005 recorded but ledger tables are missing';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = runs AND confrelid = uploads AND contype = 'f' AND convalidated
          AND conname = 'fk_video_run_upload_lesson'
          AND conkey = ARRAY[
              (SELECT attnum FROM pg_attribute WHERE attrelid = runs AND attname = 'upload_id' AND NOT attisdropped),
              (SELECT attnum FROM pg_attribute WHERE attrelid = runs AND attname = 'lesson_id' AND NOT attisdropped)
          ]::smallint[]
          AND confkey = ARRAY[
              (SELECT attnum FROM pg_attribute WHERE attrelid = uploads AND attname = 'id' AND NOT attisdropped),
              (SELECT attnum FROM pg_attribute WHERE attrelid = uploads AND attname = 'lesson_id' AND NOT attisdropped)
          ]::smallint[]
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conrelid = uploads AND contype = 'u'
          AND conname = 'uq_video_upload_id_lesson' AND convalidated
    ) THEN
        RAISE EXCEPTION 'STOP: missing/invalid composite upload-to-lesson integrity constraints';
    END IF;
    IF (SELECT count(*) FROM pg_constraint
        WHERE conrelid IN (uploads, runs) AND convalidated
          AND conname IN ('ck_video_upload_size', 'ck_video_run_attempt', 'ck_video_run_state', 'uq_video_run_upload_attempt')) <> 4 THEN
        RAISE EXCEPTION 'STOP: expected validated size/attempt/state/unique-run constraints are missing';
    END IF;
    EXECUTE 'SELECT count(*) FROM public.video_pipeline_runs r
             LEFT JOIN public.video_uploads u ON u.id = r.upload_id
             WHERE u.id IS NULL OR r.lesson_id <> u.lesson_id' INTO mismatch_count;
    IF mismatch_count <> 0 THEN
        RAISE EXCEPTION 'STOP: % runs reference an upload of another lesson or a missing upload', mismatch_count;
    END IF;
    EXECUTE 'SELECT count(*) FROM public.video_uploads' INTO upload_count;
    EXECUTE 'SELECT count(*) FROM public.video_pipeline_runs' INTO run_count;
    RAISE NOTICE 'ALREADY_APPLIED: 0005 registry/required constraints verified; uploads=%, runs=%, mismatches=0. Do not rerun the one-time migration.', upload_count, run_count;
END;
$checks$;
COMMIT;
