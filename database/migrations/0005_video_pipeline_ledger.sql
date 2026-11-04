-- REVIEWED / NOT APPLIED. Operator: backup and run read-only preflight first.
-- One-time transactional migration. A repeat/version conflict/partial schema is
-- rejected before DDL; never silently adopt unversioned or incompatible tables.
-- No change to 0004, Lesson status CHECK, existing Lesson/Course rows or seed data.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';
SET LOCAL search_path = pg_catalog, public;

DO $prerequisites$
BEGIN
    IF to_regclass('public.schema_migrations') IS NULL
       OR to_regclass('public.lessons') IS NULL THEN
        RAISE EXCEPTION 'Missing LearnCloud baseline; run video_pipeline_preflight.sql';
    END IF;
END;
$prerequisites$;

-- Serialize registry writers. Foreign-key DDL also takes parent-table locks.
LOCK TABLE public.schema_migrations IN SHARE ROW EXCLUSIVE MODE;
DO $guard$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM public.schema_migrations
        WHERE version = '0004'
          AND description = 'Allow APPROVED Lesson status for explicit review before course publishing'
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.lessons'::regclass AND conname = 'ck_lessons_status'
          AND contype = 'c' AND convalidated
          AND pg_get_constraintdef(oid) LIKE '%''APPROVED''%'
    ) THEN
        RAISE EXCEPTION 'Migration 0004 must already be recorded and validated; do not rerun bootstrap';
    END IF;
    IF EXISTS (SELECT 1 FROM public.schema_migrations WHERE version = '0005') THEN
        RAISE EXCEPTION 'Version 0005 already exists; verify its description/schema and skip this one-time file';
    END IF;
    IF to_regclass('public.video_uploads') IS NOT NULL
       OR to_regclass('public.video_pipeline_runs') IS NOT NULL THEN
        RAISE EXCEPTION 'Unversioned/partial pipeline schema exists; review separately, do not drop or auto-adopt it';
    END IF;
END;
$guard$;

CREATE TABLE public.video_uploads (
    id VARCHAR(32) PRIMARY KEY,
    lesson_id INTEGER NOT NULL REFERENCES public.lessons(id),
    source_key TEXT NOT NULL UNIQUE,
    content_type VARCHAR(64) NOT NULL,
    size_bytes INTEGER NOT NULL CONSTRAINT ck_video_upload_size CHECK (size_bytes > 0 AND size_bytes <= 524288000),
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Required referenced key for the composite FK below. id remains the PK.
    CONSTRAINT uq_video_upload_id_lesson UNIQUE (id, lesson_id)
);
CREATE INDEX ix_video_uploads_lesson_id ON public.video_uploads(lesson_id);
CREATE TABLE public.video_pipeline_runs (
    id VARCHAR(64) PRIMARY KEY,
    upload_id VARCHAR(32) NOT NULL,
    lesson_id INTEGER NOT NULL REFERENCES public.lessons(id),
    attempt INTEGER NOT NULL CONSTRAINT ck_video_run_attempt CHECK (attempt >= 0),
    state VARCHAR(24) NOT NULL CONSTRAINT ck_video_run_state CHECK (state IN
        ('QUEUED','CLAIMED','SUBMITTING','TRANSCODING','VIDEO_READY','COMPLETE','FAILED')),
    execution_arn TEXT UNIQUE,
    source_etag VARCHAR(128) NOT NULL,
    output_key TEXT NOT NULL,
    job_id VARCHAR(128),
    error_code VARCHAR(64),
    safe_to_retry BOOLEAN NOT NULL DEFAULT false,
    next_dispatch_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_video_run_upload_attempt UNIQUE(upload_id, attempt),
    CONSTRAINT fk_video_run_upload_lesson FOREIGN KEY (upload_id, lesson_id)
        REFERENCES public.video_uploads(id, lesson_id)
);
CREATE INDEX ix_video_pipeline_runs_lesson_id ON public.video_pipeline_runs(lesson_id);
CREATE INDEX ix_video_pipeline_outbox ON public.video_pipeline_runs(next_dispatch_at) WHERE state='QUEUED';

INSERT INTO public.schema_migrations (version, description)
VALUES ('0005', 'Add video upload intents and pipeline ledger with upload/lesson integrity');
COMMIT;
