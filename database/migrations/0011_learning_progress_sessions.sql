CREATE TABLE IF NOT EXISTS viewing_sessions (
    id VARCHAR(36) PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    last_sequence INTEGER NOT NULL DEFAULT 0 CHECK (last_sequence >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_viewing_sessions_student_lesson
    ON viewing_sessions(student_id, lesson_id);

CREATE TABLE IF NOT EXISTS progress_updates (
    request_id VARCHAR(36) PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    response JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE lesson_progress
    ADD COLUMN IF NOT EXISTS last_position_seconds DOUBLE PRECISION NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS watched_ranges JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS playback_session_id VARCHAR(36),
    ADD COLUMN IF NOT EXISTS last_sequence INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS last_request_id VARCHAR(36);

DO $migration$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'public.lesson_progress'::regclass
          AND conname = 'ck_lesson_progress_last_position_seconds'
    ) THEN
        ALTER TABLE lesson_progress
            ADD CONSTRAINT ck_lesson_progress_last_position_seconds
                CHECK (last_position_seconds >= 0);
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'public.lesson_progress'::regclass
          AND conname = 'ck_lesson_progress_last_sequence'
    ) THEN
        ALTER TABLE lesson_progress
            ADD CONSTRAINT ck_lesson_progress_last_sequence
                CHECK (last_sequence >= 0);
    END IF;
END
$migration$;
