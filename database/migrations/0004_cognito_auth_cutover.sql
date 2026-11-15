BEGIN;

ALTER TABLE users
    ALTER COLUMN password_hash DROP NOT NULL;

INSERT INTO schema_migrations (version, description)
VALUES ('0004', 'Prepare user identity mapping for Cognito authentication')
ON CONFLICT (version) DO NOTHING;

COMMIT;
