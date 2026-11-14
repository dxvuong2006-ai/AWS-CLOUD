-- Reconcile the TutorSession model with both the bootstrap schema and upgrades
-- where the historical V3 and/or 0006 scripts were not applied.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

DO $preflight$
DECLARE
    tutor_table regclass := to_regclass('tutor_sessions');
BEGIN
    IF tutor_table IS NULL OR to_regclass('schema_migrations') IS NULL THEN
        RAISE EXCEPTION 'TutorSession or schema_migrations is missing; inspect the database baseline';
    END IF;

    IF EXISTS (
        SELECT 1 FROM schema_migrations
        WHERE version = '0012'
          AND description <> 'Reconcile TutorSession remediation fields for AI Tutor'
    ) THEN
        RAISE EXCEPTION 'Migration version 0012 is already used by another change';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_attribute
        WHERE attrelid = tutor_table AND attname = 'practice_questions'
          AND NOT attisdropped AND atttypid <> 'jsonb'::regtype
    ) OR EXISTS (
        SELECT 1
        FROM pg_attribute
        WHERE attrelid = tutor_table AND attname = 'remediation_completed'
          AND NOT attisdropped AND atttypid <> 'boolean'::regtype
    ) OR EXISTS (
        SELECT 1
        FROM pg_attribute
        WHERE attrelid = tutor_table AND attname = 'workflow_state'
          AND NOT attisdropped AND atttypid <> 'jsonb'::regtype
    ) THEN
        RAISE EXCEPTION 'An existing TutorSession remediation column has an unexpected type';
    END IF;
END;
$preflight$;

LOCK TABLE tutor_sessions IN ACCESS EXCLUSIVE MODE;

ALTER TABLE tutor_sessions
    ADD COLUMN IF NOT EXISTS practice_questions JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS remediation_completed BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS workflow_state JSONB;

-- Repair nullable columns if a prior partial/manual change created them.
UPDATE tutor_sessions
SET practice_questions = '[]'::jsonb
WHERE practice_questions IS NULL;

UPDATE tutor_sessions
SET remediation_completed = FALSE
WHERE remediation_completed IS NULL;

ALTER TABLE tutor_sessions
    ALTER COLUMN practice_questions SET DEFAULT '[]'::jsonb,
    ALTER COLUMN practice_questions SET NOT NULL,
    ALTER COLUMN remediation_completed SET DEFAULT FALSE,
    ALTER COLUMN remediation_completed SET NOT NULL;

INSERT INTO schema_migrations(version, description)
VALUES ('0012', 'Reconcile TutorSession remediation fields for AI Tutor')
ON CONFLICT (version) DO NOTHING;

COMMIT;
