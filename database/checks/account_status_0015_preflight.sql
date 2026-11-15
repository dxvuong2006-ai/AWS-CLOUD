-- Read-only pgAdmin checks. Run before 0015 and save the row count/results.
-- STOP unless database/schema/registry are correct, 0014 is present once,
-- 0015 is absent, and learncloud_admin is confirmed as the deployed Backend DB
-- login. SQL cannot inspect the Lambda secret; verify it outside pgAdmin.
-- Confirm the first result identifies the intended LearnCloud RDS database.

DO $gate$
BEGIN
    IF current_setting('server_version_num')::integer < 160000 THEN
        RAISE EXCEPTION 'STOP: reviewed target is PostgreSQL 16+; found %',
            current_setting('server_version');
    END IF;
    IF pg_catalog.to_regclass('public.users') IS NULL
       OR pg_catalog.to_regclass('public.schema_migrations') IS NULL THEN
        RAISE EXCEPTION 'STOP: users or schema_migrations is missing';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM public.schema_migrations
        WHERE version = '0014'
          AND description = 'Secure lesson progress duration trigger permissions'
    ) THEN
        RAISE EXCEPTION 'STOP: canonical migration 0014 is not registered';
    END IF;
    IF EXISTS (SELECT 1 FROM public.schema_migrations WHERE version = '0015') THEN
        RAISE EXCEPTION 'STOP: migration 0015 is already registered';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_attribute
        WHERE attrelid = 'public.users'::pg_catalog.regclass
          AND attname = 'status' AND NOT attisdropped
    ) THEN
        RAISE EXCEPTION 'STOP: users.status already exists; inspect schema/registry';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
        WHERE rolname = 'learncloud_admin' AND rolcanlogin
    ) THEN
        RAISE EXCEPTION 'STOP: learncloud_admin is missing or cannot LOGIN';
    END IF;
END;
$gate$;

SELECT current_database() AS database_name,
       current_user AS connected_role,
       current_setting('server_version') AS postgres_version,
       pg_catalog.to_regclass('public.users') IS NOT NULL AS users_exists,
       pg_catalog.to_regclass('public.schema_migrations') IS NOT NULL AS registry_exists;

SELECT version, description, applied_at
FROM public.schema_migrations
WHERE version IN ('0014', '0015')
ORDER BY version;

SELECT count(*) AS users_before_0015,
       count(*) FILTER (WHERE role = 'ADMIN') AS admins_before_0015,
       count(*) FILTER (WHERE role = 'STUDENT') AS students_before_0015,
       count(*) FILTER (WHERE role = 'INSTRUCTOR') AS instructors_before_0015
FROM public.users;

SELECT EXISTS (
           SELECT 1 FROM pg_catalog.pg_attribute
           WHERE attrelid = 'public.users'::pg_catalog.regclass
             AND attname = 'status' AND NOT attisdropped
       ) AS status_column_already_exists,
       pg_catalog.pg_get_userbyid(c.relowner) AS users_table_owner,
       pg_catalog.pg_total_relation_size(c.oid) AS users_table_size_bytes
FROM pg_catalog.pg_class AS c
WHERE c.oid = 'public.users'::pg_catalog.regclass;

-- Role privileges before migration. Column-level grants are reported separately
-- from table-level grants. learncloud_admin is the local Backend role found in
-- repository-root .env; verify it matches the production runtime before apply.
SELECT role.rolname,
       role.rolcanlogin,
       pg_catalog.has_table_privilege(role.rolname, 'public.users', 'SELECT') AS users_table_select,
       pg_catalog.has_table_privilege(role.rolname, 'public.users', 'UPDATE') AS users_table_update,
       pg_catalog.has_column_privilege(role.rolname, 'public.users', 'name', 'SELECT') AS name_select,
       pg_catalog.has_column_privilege(role.rolname, 'public.users', 'role', 'UPDATE') AS role_update
FROM pg_catalog.pg_roles AS role
WHERE role.rolname IN (
    'learncloud_admin',
    'learncloud_video_runtime',
    'learncloud_ai_worker_runtime'
)
ORDER BY role.rolname;

-- Expected gate: one 0014 row with the canonical description; no 0015 row;
-- users.status absent; users_before_0015 recorded; learncloud_admin is the
-- observed local Backend login. If production uses another username,
-- stop and adapt the reviewed role references before applying.
