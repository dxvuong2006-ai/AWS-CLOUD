-- Read-only pgAdmin checks. Run immediately after migration 0015 commits.

DO $gate$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM public.schema_migrations
        WHERE version = '0015'
          AND description = 'Add active status to user accounts'
    ) THEN
        RAISE EXCEPTION 'POSTFLIGHT FAILED: canonical migration 0015 registry row is missing';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.users
        WHERE status IS NULL OR status NOT IN ('ACTIVE', 'INACTIVE')
    ) THEN
        RAISE EXCEPTION 'POSTFLIGHT FAILED: null or invalid users.status exists';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_attribute
        WHERE attrelid = 'public.users'::pg_catalog.regclass
          AND attname = 'status'
          AND atttypid = 'pg_catalog.varchar'::pg_catalog.regtype
          AND atttypmod = 24
          AND attnotnull
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_constraint
        WHERE conrelid = 'public.users'::pg_catalog.regclass
          AND conname = 'ck_users_status'
          AND contype = 'c'
          AND convalidated
    ) THEN
        RAISE EXCEPTION 'POSTFLIGHT FAILED: status column/constraint does not match expected definition';
    END IF;
    IF NOT pg_catalog.has_column_privilege(
        'learncloud_admin', 'public.users', 'status', 'SELECT'
    ) OR NOT pg_catalog.has_column_privilege(
        'learncloud_admin', 'public.users', 'status', 'UPDATE'
    ) THEN
        RAISE EXCEPTION 'POSTFLIGHT FAILED: learncloud_admin lacks status SELECT/UPDATE';
    END IF;
END;
$gate$;

SELECT version, description, applied_at
FROM public.schema_migrations
WHERE version = '0015';

SELECT count(*) AS users_after_0015,
       count(*) FILTER (WHERE status = 'ACTIVE') AS active_users,
       count(*) FILTER (WHERE status = 'INACTIVE') AS inactive_users,
       count(*) FILTER (WHERE status IS NULL) AS null_status_users,
       count(*) FILTER (WHERE status NOT IN ('ACTIVE', 'INACTIVE')) AS invalid_status_users
FROM public.users;

SELECT column_name, data_type, character_maximum_length, is_nullable,
       column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'users'
  AND column_name = 'status';

SELECT constraint_name, check_clause
FROM information_schema.check_constraints
WHERE constraint_schema = 'public'
  AND constraint_name = 'ck_users_status';

SELECT role.rolname,
       pg_catalog.has_column_privilege(role.rolname, 'public.users', 'status', 'SELECT') AS status_select,
       pg_catalog.has_column_privilege(role.rolname, 'public.users', 'status', 'UPDATE') AS status_update
FROM pg_catalog.pg_roles AS role
WHERE role.rolname IN (
    'learncloud_admin',
    'learncloud_video_runtime',
    'learncloud_ai_worker_runtime'
)
ORDER BY role.rolname;

-- Compare users_after_0015 with the saved preflight count. All existing rows
-- should now be ACTIVE; learncloud_admin status SELECT/UPDATE should be true;
-- worker access should remain unchanged. The migration performs no account DML.
