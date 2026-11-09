-- Review and apply separately; this change does not run migrations.
BEGIN;
ALTER TABLE courses ADD COLUMN IF NOT EXISTS cover_image TEXT;
ALTER TABLE tutor_sessions ADD COLUMN IF NOT EXISTS workflow_state JSONB;
INSERT INTO schema_migrations(version, description)
VALUES ('0006', 'Course cover and resumable remediation workflow')
ON CONFLICT (version) DO NOTHING;
COMMIT;
