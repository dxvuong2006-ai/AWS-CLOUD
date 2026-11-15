-- Reconcile the four historical 0004 migrations without rewriting their registry entry.
-- Canonical state: no APPROVED lesson status; Cognito-compatible users; checkpoint idempotency.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';
SET LOCAL search_path = pg_catalog, public;

DO $preflight$
DECLARE
    status_attnum smallint;
    status_constraint record;
BEGIN
    IF to_regclass('public.schema_migrations') IS NULL
       OR to_regclass('public.users') IS NULL
       OR to_regclass('public.lessons') IS NULL
       OR to_regclass('public.quiz_attempts') IS NULL THEN
        RAISE EXCEPTION 'Core LearnCloud schema is missing; do not apply 0010';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.schema_migrations
        WHERE version = '0010'
          AND description <> 'Reconcile canonical review, checkpoint idempotency, and Cognito schema'
    ) THEN
        RAISE EXCEPTION 'Migration version 0010 is already used by another change';
    END IF;

    SELECT attnum INTO status_attnum
    FROM pg_attribute
    WHERE attrelid = 'public.lessons'::regclass
      AND attname = 'status' AND NOT attisdropped;
    IF status_attnum IS NULL THEN
        RAISE EXCEPTION 'lessons.status is missing';
    END IF;

    FOR status_constraint IN
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'public.lessons'::regclass
          AND contype = 'c' AND status_attnum = ANY(conkey)
    LOOP
        IF status_constraint.conname NOT IN (
            'lessons_status_check', 'ck_lessons_status', 'chk_lessons_status'
        ) THEN
            RAISE EXCEPTION 'Unexpected Lesson status constraint %; inspect manually',
                status_constraint.conname;
        END IF;
    END LOOP;

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
$preflight$;

LOCK TABLE public.schema_migrations IN SHARE ROW EXCLUSIVE MODE;
LOCK TABLE public.users, public.lessons, public.quiz_attempts IN ACCESS EXCLUSIVE MODE;

ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS cognito_sub VARCHAR(255),
    ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);
ALTER TABLE public.users ALTER COLUMN password_hash DROP NOT NULL;

DO $cognito_unique$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_index i
        WHERE i.indrelid = 'public.users'::regclass
          AND i.indisunique AND i.indpred IS NULL
          AND (
              SELECT array_agg(a.attname ORDER BY key_column.ordinality)
              FROM unnest(i.indkey) WITH ORDINALITY AS key_column(attnum, ordinality)
              JOIN pg_attribute a
                ON a.attrelid = i.indrelid AND a.attnum = key_column.attnum
          ) = ARRAY['cognito_sub']::name[]
    ) THEN
        CREATE UNIQUE INDEX uq_users_cognito_sub ON public.users(cognito_sub);
    END IF;
END;
$cognito_unique$;

UPDATE public.lessons
SET status = 'PUBLISHED', updated_at = pg_catalog.now()
WHERE status = 'APPROVED';

ALTER TABLE public.lessons DROP CONSTRAINT IF EXISTS lessons_status_check;
ALTER TABLE public.lessons DROP CONSTRAINT IF EXISTS ck_lessons_status;
ALTER TABLE public.lessons DROP CONSTRAINT IF EXISTS chk_lessons_status;
ALTER TABLE public.lessons ADD CONSTRAINT ck_lessons_status CHECK (status IN (
    'DRAFT', 'UPLOADED', 'PROCESSING', 'TRANSCRIBING',
    'AI_PROCESSING', 'REVIEW_REQUIRED', 'PUBLISHED', 'FAILED'
)) NOT VALID;
ALTER TABLE public.lessons VALIDATE CONSTRAINT ck_lessons_status;

ALTER TABLE public.quiz_attempts
    ADD COLUMN IF NOT EXISTS request_id VARCHAR(36),
    ADD COLUMN IF NOT EXISTS request_hash VARCHAR(64);
CREATE UNIQUE INDEX IF NOT EXISTS uq_quiz_attempts_request
    ON public.quiz_attempts(student_id, quiz_id, request_id);

CREATE TABLE IF NOT EXISTS public.checkpoint_remediation (
    attempt_id INTEGER PRIMARY KEY REFERENCES public.quiz_attempts(id) ON DELETE CASCADE,
    explanation_completed BOOLEAN NOT NULL DEFAULT FALSE,
    review_completed BOOLEAN NOT NULL DEFAULT FALSE,
    practice_total INTEGER NOT NULL DEFAULT 0,
    practice_correct INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.now(),
    CONSTRAINT ck_checkpoint_remediation_total
        CHECK (practice_total BETWEEN 0 AND 3),
    CONSTRAINT ck_checkpoint_remediation_correct
        CHECK (practice_correct >= 0 AND practice_correct <= practice_total)
);
LOCK TABLE public.checkpoint_remediation IN ACCESS EXCLUSIVE MODE;

DO $verify$
BEGIN
    IF EXISTS (SELECT 1 FROM public.lessons WHERE status = 'APPROVED')
       OR NOT EXISTS (
           SELECT 1 FROM pg_constraint
           WHERE conrelid = 'public.lessons'::regclass
             AND conname = 'ck_lessons_status' AND contype = 'c' AND convalidated
             AND pg_get_constraintdef(oid) NOT LIKE '%''APPROVED''%'
       )
       OR EXISTS (
           SELECT 1 FROM information_schema.columns
           WHERE table_schema = 'public' AND table_name = 'users'
             AND column_name = 'password_hash' AND is_nullable <> 'YES'
       )
       OR (SELECT count(*) FROM information_schema.columns
           WHERE table_schema = 'public' AND table_name = 'users'
             AND ((column_name = 'cognito_sub' AND data_type = 'character varying'
                   AND character_maximum_length = 255 AND is_nullable = 'YES')
               OR (column_name = 'password_hash' AND data_type = 'character varying'
                   AND character_maximum_length = 255 AND is_nullable = 'YES'))) <> 2
       OR (SELECT count(*) FROM information_schema.columns
           WHERE table_schema = 'public' AND table_name = 'quiz_attempts'
             AND ((column_name = 'request_id' AND data_type = 'character varying'
                   AND character_maximum_length = 36 AND is_nullable = 'YES')
               OR (column_name = 'request_hash' AND data_type = 'character varying'
                   AND character_maximum_length = 64 AND is_nullable = 'YES'))) <> 2
       OR NOT EXISTS (
           SELECT 1 FROM pg_index
           WHERE indexrelid = to_regclass('public.uq_quiz_attempts_request')
             AND indisunique AND indpred IS NULL
             AND pg_get_indexdef(indexrelid) LIKE
                 '%(student_id, quiz_id, request_id)%'
       )
       OR to_regclass('public.checkpoint_remediation') IS NULL
       OR (SELECT count(*) FROM information_schema.columns
           WHERE table_schema = 'public' AND table_name = 'checkpoint_remediation'
             AND ((column_name = 'attempt_id' AND data_type = 'integer'
                   AND is_nullable = 'NO')
               OR (column_name IN ('explanation_completed', 'review_completed')
                   AND data_type = 'boolean' AND is_nullable = 'NO')
               OR (column_name IN ('practice_total', 'practice_correct')
                   AND data_type = 'integer' AND is_nullable = 'NO')
               OR (column_name = 'updated_at'
                   AND data_type = 'timestamp with time zone' AND is_nullable = 'NO'))) <> 6
       OR NOT EXISTS (
           SELECT 1 FROM pg_constraint
           WHERE conrelid = 'public.checkpoint_remediation'::regclass
             AND contype = 'p' AND pg_get_constraintdef(oid) = 'PRIMARY KEY (attempt_id)'
       )
       OR NOT EXISTS (
           SELECT 1 FROM pg_constraint
           WHERE conrelid = 'public.checkpoint_remediation'::regclass
             AND contype = 'f'
             AND pg_get_constraintdef(oid) =
                 'FOREIGN KEY (attempt_id) REFERENCES quiz_attempts(id) ON DELETE CASCADE'
       )
       OR NOT EXISTS (
           SELECT 1 FROM pg_constraint
           WHERE conrelid = 'public.checkpoint_remediation'::regclass
             AND conname = 'ck_checkpoint_remediation_total'
             AND contype = 'c' AND convalidated
       )
       OR NOT EXISTS (
           SELECT 1 FROM pg_constraint
           WHERE conrelid = 'public.checkpoint_remediation'::regclass
             AND conname = 'ck_checkpoint_remediation_correct'
             AND contype = 'c' AND convalidated
       ) THEN
        RAISE EXCEPTION 'Migration 0010 verification failed; transaction will roll back';
    END IF;
END;
$verify$;

INSERT INTO public.schema_migrations(version, description)
SELECT '0010', 'Reconcile canonical review, checkpoint idempotency, and Cognito schema'
WHERE NOT EXISTS (
    SELECT 1 FROM public.schema_migrations WHERE version = '0010'
);

COMMIT;
