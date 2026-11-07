-- Áp dụng trên PostgreSQL sau các migration trước đó.
BEGIN;
ALTER TABLE tutor_sessions
    ADD COLUMN IF NOT EXISTS practice_questions JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS remediation_completed BOOLEAN NOT NULL DEFAULT FALSE;
COMMIT;
