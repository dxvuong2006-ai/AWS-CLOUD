-- Apply ONCE to the existing learncloud database; preserves seeded users.
-- Earlier seed users have password_hash=NULL and cannot log in until
-- a trusted local operator sets a password with scripts/set_user_password.py.
ALTER TABLE users
ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);
