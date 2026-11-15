-- Reconcile the historical APPROVED status with the current production contract.
-- This migration does not create/replay the 0005 ledger and does not touch K5 content.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';
SET LOCAL search_path = pg_catalog, public;

DO $guard$
BEGIN
    IF current_database() <> 'learncloud' THEN
        RAISE EXCEPTION 'Expected production database learncloud';
    END IF;
    IF to_regclass('public.schema_migrations') IS NULL
       OR to_regclass('public.lessons') IS NULL
       OR to_regclass('public.video_uploads') IS NULL
       OR to_regclass('public.video_pipeline_runs') IS NULL THEN
        RAISE EXCEPTION 'K4/K5 production prerequisites are missing';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM public.schema_migrations
        WHERE version = '0005'
          AND description = 'Add video upload intents and pipeline ledger with upload/lesson integrity'
    ) THEN
        RAISE EXCEPTION 'Migration 0005 is missing or incompatible; do not replay it';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.schema_migrations
        WHERE version = '0009'
          AND description <> 'Reconcile Lesson review status for K4/K5 production'
    ) THEN
        RAISE EXCEPTION 'Migration version 0009 is already used by another change';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.lessons
        WHERE status IS NULL OR status NOT IN (
            'DRAFT', 'UPLOADED', 'PROCESSING', 'TRANSCRIBING',
            'AI_PROCESSING', 'REVIEW_REQUIRED', 'APPROVED', 'PUBLISHED', 'FAILED'
        )
    ) THEN
        RAISE EXCEPTION 'Unsupported Lesson status exists; migration will not guess';
    END IF;
END;
$guard$;

LOCK TABLE public.lessons IN ACCESS EXCLUSIVE MODE;

UPDATE public.lessons
SET status = 'PUBLISHED', updated_at = pg_catalog.now()
WHERE status = 'APPROVED';

ALTER TABLE public.lessons DROP CONSTRAINT IF EXISTS lessons_status_check;
ALTER TABLE public.lessons DROP CONSTRAINT IF EXISTS ck_lessons_status;
ALTER TABLE public.lessons DROP CONSTRAINT IF EXISTS chk_lessons_status;
ALTER TABLE public.lessons ADD CONSTRAINT ck_lessons_status CHECK (
    status IN (
        'DRAFT', 'UPLOADED', 'PROCESSING', 'TRANSCRIBING',
        'AI_PROCESSING', 'REVIEW_REQUIRED', 'PUBLISHED', 'FAILED'
    )
) NOT VALID;
ALTER TABLE public.lessons VALIDATE CONSTRAINT ck_lessons_status;

INSERT INTO public.schema_migrations (version, description)
VALUES ('0009', 'Reconcile Lesson review status for K4/K5 production')
ON CONFLICT (version) DO NOTHING;

DO $verify$
BEGIN
    IF EXISTS (SELECT 1 FROM public.lessons WHERE status = 'APPROVED')
       OR NOT EXISTS (
           SELECT 1 FROM pg_constraint
           WHERE conrelid = 'public.lessons'::regclass
             AND conname = 'ck_lessons_status'
             AND contype = 'c'
             AND convalidated
             AND pg_get_constraintdef(oid) NOT LIKE '%''APPROVED''%'
             AND pg_get_constraintdef(oid) LIKE '%''REVIEW_REQUIRED''%'
       ) OR NOT EXISTS (
           SELECT 1 FROM public.schema_migrations
           WHERE version = '0009'
             AND description = 'Reconcile Lesson review status for K4/K5 production'
       ) THEN
        RAISE EXCEPTION 'K4/K5 production reconciliation verification failed';
    END IF;
END;
$verify$;

COMMIT;
