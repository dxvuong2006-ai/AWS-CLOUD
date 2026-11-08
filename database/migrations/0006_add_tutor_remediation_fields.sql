BEGIN;
ALTER TABLE tutor_sessions
    ADD COLUMN IF NOT EXISTS practice_questions JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS remediation_completed BOOLEAN NOT NULL DEFAULT FALSE;
INSERT INTO schema_migrations (version, description)
VALUES ('0006', 'add tutor remediation fields')
ON CONFLICT (version) DO NOTHING;
COMMIT;
