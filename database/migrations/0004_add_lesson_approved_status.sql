-- REVIEW ONLY until an operator explicitly applies this migration.
-- Widens the Lesson status CHECK; never updates/approves any existing Lesson.
-- Handles bootstrap/ORM constraint names; refuses unknown status constraints.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

-- Replacement is atomic. No transaction can write an unvalidated status gap.
-- This lock can block readers/writers: use a maintenance window on shared DBs.
LOCK TABLE public.lessons IN ACCESS EXCLUSIVE MODE;

DO $migration$
DECLARE
    status_column smallint;
    status_constraint record;
    constraint_count integer := 0;
BEGIN
    IF EXISTS (
        SELECT 1 FROM public.schema_migrations WHERE version = '0004'
          AND description <> 'Allow APPROVED Lesson status for explicit review before course publishing'
    ) THEN
        RAISE EXCEPTION 'Migration version 0004 is already used by another change';
    END IF;

    SELECT attnum INTO status_column FROM pg_attribute
    WHERE attrelid = 'public.lessons'::regclass AND attname = 'status' AND NOT attisdropped;
    IF status_column IS NULL THEN
        RAISE EXCEPTION 'lessons.status is missing; review preflight before migrating';
    END IF;

    FOR status_constraint IN
        SELECT conname, conkey FROM pg_constraint
        WHERE conrelid = 'public.lessons'::regclass AND contype = 'c'
          AND status_column = ANY(conkey)
    LOOP
        IF status_constraint.conname NOT IN ('lessons_status_check', 'ck_lessons_status', 'chk_lessons_status')
           OR status_constraint.conkey <> ARRAY[status_column]::smallint[] THEN
            RAISE EXCEPTION 'Unexpected status constraint %; review manually', status_constraint.conname;
        END IF;
        constraint_count := constraint_count + 1;
    END LOOP;
    IF constraint_count = 0 THEN
        RAISE EXCEPTION 'No recognized Lesson status CHECK; review preflight';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.lessons WHERE status IS NULL OR status NOT IN (
            'DRAFT', 'UPLOADED', 'PROCESSING', 'TRANSCRIBING', 'AI_PROCESSING',
            'REVIEW_REQUIRED', 'APPROVED', 'PUBLISHED', 'FAILED'
        )
    ) THEN
        RAISE EXCEPTION 'Unsupported Lesson status exists; migration does not rewrite data';
    END IF;
END;
$migration$;

ALTER TABLE public.lessons DROP CONSTRAINT IF EXISTS lessons_status_check;
ALTER TABLE public.lessons DROP CONSTRAINT IF EXISTS ck_lessons_status;
ALTER TABLE public.lessons DROP CONSTRAINT IF EXISTS chk_lessons_status;
ALTER TABLE public.lessons ADD CONSTRAINT ck_lessons_status CHECK (status IN (
    'DRAFT', 'UPLOADED', 'PROCESSING', 'TRANSCRIBING', 'AI_PROCESSING',
    'REVIEW_REQUIRED', 'APPROVED', 'PUBLISHED', 'FAILED'
)) NOT VALID;
ALTER TABLE public.lessons VALIDATE CONSTRAINT ck_lessons_status;

INSERT INTO public.schema_migrations (version, description)
VALUES ('0004', 'Allow APPROVED Lesson status for explicit review before course publishing')
ON CONFLICT (version) DO NOTHING;
COMMIT;
