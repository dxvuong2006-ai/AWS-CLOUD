BEGIN;

-- Additive only. No existing identity is enrolled, linked or overwritten.
CREATE TABLE IF NOT EXISTS local_auth_identities (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    verified_at TIMESTAMPTZ,
    login_failures INTEGER NOT NULL DEFAULT 0 CHECK (login_failures >= 0),
    locked_until TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS local_auth_otps (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    purpose VARCHAR(10) NOT NULL CHECK (purpose IN ('verify', 'reset')),
    code_hash VARCHAR(64) NOT NULL,
    nonce VARCHAR(64) NOT NULL,
    sent_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    consumed_at TIMESTAMPTZ,
    PRIMARY KEY (user_id, purpose)
);

CREATE TABLE IF NOT EXISTS local_auth_sessions (
    token_hash VARCHAR(64) PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_local_auth_sessions_user_id ON local_auth_sessions(user_id);
CREATE INDEX IF NOT EXISTS ix_local_auth_sessions_expires_at ON local_auth_sessions(expires_at);

INSERT INTO schema_migrations (version, description)
VALUES ('0007', 'Opt-in development/test local auth, hashed email OTP and revocable sessions')
ON CONFLICT (version) DO NOTHING;

COMMIT;
