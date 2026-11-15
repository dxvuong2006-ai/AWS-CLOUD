-- Adds persisted account state without updating, deleting, or disabling any
-- existing account. Run as the owner of public.users/schema_migrations.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';
SET LOCAL search_path = pg_catalog, public;

DO $preflight$
BEGIN
    IF pg_catalog.to_regclass('public.users') IS NULL
       OR pg_catalog.to_regclass('public.schema_migrations') IS NULL THEN
        RAISE EXCEPTION 'users or schema_migrations is missing';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM public.schema_migrations
        WHERE version = '0014'
          AND description = 'Secure lesson progress duration trigger permissions'
    ) THEN
        RAISE EXCEPTION 'Expected migration 0014 is not registered; stop and reconcile migration history';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.schema_migrations WHERE version = '0015'
    ) THEN
        RAISE EXCEPTION 'Migration 0015 is already registered; do not apply it again';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_attribute
        WHERE attrelid = 'public.users'::pg_catalog.regclass
          AND attname = 'status'
          AND NOT attisdropped
    ) THEN
        RAISE EXCEPTION 'users.status already exists without migration 0015; inspect schema before proceeding';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
        WHERE rolname = 'learncloud_admin' AND rolcanlogin
    ) THEN
        RAISE EXCEPTION 'Configured Backend role learncloud_admin is missing or cannot LOGIN';
    END IF;
END;
$preflight$;

ALTER TABLE public.users
    ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE';

ALTER TABLE public.users
    ADD CONSTRAINT ck_users_status
    CHECK (status IN ('ACTIVE', 'INACTIVE'));

-- The configured local Backend uses learncloud_admin. Add only the status
-- column privileges if they are not already inherited from table ownership or
-- existing table/column grants. Do not create a role or grant access to workers.
DO $runtime_privileges$
BEGIN
    IF NOT pg_catalog.has_column_privilege(
        'learncloud_admin', 'public.users', 'status', 'SELECT'
    ) THEN
        EXECUTE 'GRANT SELECT (status) ON TABLE public.users TO learncloud_admin';
    END IF;
    IF NOT pg_catalog.has_column_privilege(
        'learncloud_admin', 'public.users', 'status', 'UPDATE'
    ) THEN
        EXECUTE 'GRANT UPDATE (status) ON TABLE public.users TO learncloud_admin';
    END IF;
END;
$runtime_privileges$;

DO $verify$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_attribute
        WHERE attrelid = 'public.users'::pg_catalog.regclass
          AND attname = 'status'
          AND atttypid = 'pg_catalog.varchar'::pg_catalog.regtype
          AND atttypmod = 24
          AND attnotnull
    ) THEN
        RAISE EXCEPTION 'users.status did not get the expected VARCHAR(20) NOT NULL definition';
    END IF;

    IF pg_catalog.pg_get_expr((
        SELECT attrdef.adbin
        FROM pg_catalog.pg_attrdef AS attrdef
        JOIN pg_catalog.pg_attribute AS attribute
          ON attribute.attrelid = attrdef.adrelid
         AND attribute.attnum = attrdef.adnum
        WHERE attrdef.adrelid = 'public.users'::pg_catalog.regclass
          AND attribute.attname = 'status'
    ), 'public.users'::pg_catalog.regclass)
       IS DISTINCT FROM '''ACTIVE''::character varying' THEN
        RAISE EXCEPTION 'users.status does not have the expected ACTIVE default';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_constraint
        WHERE conrelid = 'public.users'::pg_catalog.regclass
          AND conname = 'ck_users_status'
          AND contype = 'c'
          AND convalidated
    ) THEN
        RAISE EXCEPTION 'users.status check constraint is missing or not validated';
    END IF;

    IF NOT pg_catalog.has_column_privilege(
        'learncloud_admin', 'public.users', 'status', 'SELECT'
    ) OR NOT pg_catalog.has_column_privilege(
        'learncloud_admin', 'public.users', 'status', 'UPDATE'
    ) THEN
        RAISE EXCEPTION 'learncloud_admin lacks SELECT/UPDATE on users.status';
    END IF;
END;
$verify$;

INSERT INTO public.schema_migrations(version, description)
VALUES ('0015', 'Add active status to user accounts');

COMMIT;
