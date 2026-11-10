-- Preserve existing attempts; new API submissions require a UUID request ID.
BEGIN;
ALTER TABLE quiz_attempts ADD COLUMN IF NOT EXISTS request_id VARCHAR(36);
ALTER TABLE quiz_attempts ADD COLUMN IF NOT EXISTS request_hash VARCHAR(64);
CREATE UNIQUE INDEX IF NOT EXISTS uq_quiz_attempts_request
    ON quiz_attempts(student_id, quiz_id, request_id);
CREATE TABLE IF NOT EXISTS checkpoint_remediation (
    attempt_id INTEGER PRIMARY KEY REFERENCES quiz_attempts(id) ON DELETE CASCADE,
    explanation_completed BOOLEAN NOT NULL DEFAULT FALSE,
    review_completed BOOLEAN NOT NULL DEFAULT FALSE,
    practice_total INTEGER NOT NULL DEFAULT 0,
    practice_correct INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_checkpoint_remediation_total CHECK (practice_total BETWEEN 0 AND 3),
    CONSTRAINT ck_checkpoint_remediation_correct CHECK (
        practice_correct >= 0 AND practice_correct <= practice_total)
);
INSERT INTO schema_migrations(version, description)
VALUES ('0004', 'checkpoint idempotency and mandatory remediation')
ON CONFLICT (version) DO NOTHING;
COMMIT;
