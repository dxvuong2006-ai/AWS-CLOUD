-- Read-only inspection. This file does NOT apply a migration or update data.
BEGIN TRANSACTION READ ONLY;
SELECT current_database() AS database, current_schema() AS schema,
       current_setting('server_version') AS postgres_version;
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'lessons'
  AND column_name IN ('status', 'approved_by', 'approved_at');
SELECT conname, convalidated, pg_get_constraintdef(oid) AS definition
FROM pg_constraint WHERE conrelid = 'public.lessons'::regclass AND contype = 'c';
SELECT status, count(*) AS lessons FROM public.lessons GROUP BY status ORDER BY status;
SELECT count(*) AS unsupported_statuses FROM public.lessons
WHERE status IS NULL OR status NOT IN (
    'DRAFT', 'UPLOADED', 'PROCESSING', 'TRANSCRIBING', 'AI_PROCESSING',
    'REVIEW_REQUIRED', 'APPROVED', 'PUBLISHED', 'FAILED'
);
SELECT version, description, applied_at FROM public.schema_migrations ORDER BY version;
COMMIT;
