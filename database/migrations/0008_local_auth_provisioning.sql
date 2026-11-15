-- Review/apply manually. Never run against RDS automatically.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';
SET LOCAL search_path = pg_catalog, public;

DO $preflight$
BEGIN
    IF to_regclass('public.local_auth_identities') IS NULL
       OR to_regclass('public.local_auth_otps') IS NULL
       OR to_regclass('public.local_auth_sessions') IS NULL
       OR to_regclass('public.schema_migrations') IS NULL THEN
        RAISE EXCEPTION 'Review/apply migration 0007 first';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM public.schema_migrations WHERE version='0007') THEN
        RAISE EXCEPTION 'Missing migration 0007 registry entry';
    END IF;
END;
$preflight$;

LOCK TABLE public.schema_migrations IN SHARE ROW EXCLUSIVE MODE;
DO $version_guard$
BEGIN
    IF EXISTS (SELECT 1 FROM public.schema_migrations WHERE version='0008')
       OR EXISTS (SELECT 1 FROM information_schema.columns
                  WHERE table_schema='public' AND table_name='local_auth_identities'
                  AND column_name IN ('provisioned_at','provisioned_by','provisioning_reference')) THEN
        RAISE EXCEPTION 'Version 0008 or partial provisioning schema exists; inspect instead of replaying';
    END IF;
END;
$version_guard$;

ALTER TABLE public.local_auth_identities
    ADD COLUMN provisioned_at TIMESTAMPTZ,
    ADD COLUMN provisioned_by VARCHAR(63),
    ADD COLUMN provisioning_reference VARCHAR(128),
    ADD CONSTRAINT ck_local_identity_provisioning CHECK (
        (provisioned_at IS NULL AND provisioned_by IS NULL AND provisioning_reference IS NULL)
        OR (provisioned_at IS NOT NULL AND provisioned_by IS NOT NULL
            AND provisioning_reference IS NOT NULL AND verified_at IS NOT NULL
            AND length(trim(provisioned_by)) > 0 AND length(trim(provisioning_reference)) > 0)
    );

INSERT INTO public.schema_migrations(version,description)
VALUES ('0008','Explicit operator provisioning of existing local auth identities');
COMMIT;
