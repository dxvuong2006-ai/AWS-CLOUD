CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    cognito_sub VARCHAR(255) UNIQUE,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(320) NOT NULL UNIQUE,
    role VARCHAR(20) NOT NULL DEFAULT 'STUDENT'
        CHECK (role IN ('STUDENT', 'INSTRUCTOR', 'ADMIN')),
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
        CHECK (status IN ('ACTIVE', 'INACTIVE')),
    password_hash VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS courses (
    id SERIAL PRIMARY KEY,
    instructor_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    learning_objectives JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(learning_objectives) = 'array'),
    status VARCHAR(20) NOT NULL DEFAULT 'DRAFT'
        CHECK (status IN ('DRAFT', 'PUBLISHED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sections (
    id SERIAL PRIMARY KEY,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    position INTEGER NOT NULL CHECK (position > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    update_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (course_id, position)
);

CREATE TABLE IF NOT EXISTS lessons (
    id SERIAL PRIMARY KEY,
    section_id INTEGER NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    position INTEGER NOT NULL CHECK (position > 0),
    raw_video_key TEXT,
    processed_video_key TEXT,
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT'
        CONSTRAINT ck_lessons_status CHECK (status IN (
            'DRAFT', 'UPLOADED', 'PROCESSING', 'TRANSCRIBING',
            'AI_PROCESSING', 'REVIEW_REQUIRED',
            'PUBLISHED', 'FAILED'
        )),
    transcript_json JSONB,
    summary TEXT,
    key_concepts_json JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(key_concepts_json) = 'array'),
    duration_seconds INTEGER CHECK (duration_seconds IS NULL OR duration_seconds >= 0),
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (section_id, position)
);

-- Flashcards are generated for a lesson and can be edited by the instructor.
CREATE TABLE IF NOT EXISTS flashcards (
    id SERIAL PRIMARY KEY,
    lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    front TEXT NOT NULL CHECK (length(trim(front)) > 0),
    back TEXT NOT NULL CHECK (length(trim(back)) > 0),
    position INTEGER NOT NULL CHECK (position > 0),
    is_approved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (lesson_id, position)
);

CREATE TABLE IF NOT EXISTS enrollments (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    enrolled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (student_id, course_id)
);

CREATE TABLE IF NOT EXISTS lesson_progress (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    watched_seconds INTEGER NOT NULL DEFAULT 0 CHECK (watched_seconds >= 0),
    last_position_seconds DOUBLE PRECISION NOT NULL DEFAULT 0
        CHECK (last_position_seconds >= 0),
    watched_ranges JSONB NOT NULL DEFAULT '[]'::jsonb,
    completed BOOLEAN NOT NULL DEFAULT FALSE,
    playback_session_id VARCHAR(36),
    last_sequence INTEGER NOT NULL DEFAULT 0 CHECK (last_sequence >= 0),
    last_request_id VARCHAR(36),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (student_id, lesson_id)
);

CREATE TABLE IF NOT EXISTS viewing_sessions (
    id VARCHAR(36) PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    last_sequence INTEGER NOT NULL DEFAULT 0 CHECK (last_sequence >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS progress_updates (
    request_id VARCHAR(36) PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    response JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS quizzes (
    id SERIAL PRIMARY KEY,
    section_id INTEGER NOT NULL UNIQUE REFERENCES sections(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    passing_score NUMERIC(5,2) NOT NULL DEFAULT 80.00
        CHECK (passing_score >= 0 AND passing_score <= 100),
    is_approved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS questions (
    id SERIAL PRIMARY KEY,
    quiz_id INTEGER NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    question TEXT NOT NULL CHECK (length(trim(question)) > 0),
    options_json JSONB NOT NULL
        CHECK (
            jsonb_typeof(options_json) = 'array'
            AND jsonb_array_length(options_json) >= 2
        ),
    correct_answer TEXT NOT NULL,
    explanation TEXT,
    topic VARCHAR(255),
    source_start_seconds NUMERIC(10,3),
    source_end_seconds NUMERIC(10,3),
    position INTEGER NOT NULL CHECK (position > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (
        (source_start_seconds IS NULL AND source_end_seconds IS NULL)
        OR
        (source_start_seconds IS NOT NULL AND source_end_seconds IS NOT NULL
         AND source_start_seconds >= 0
         AND source_end_seconds >= source_start_seconds)
    ),
    CHECK (options_json ? correct_answer),
    UNIQUE (quiz_id, position)
);

CREATE TABLE IF NOT EXISTS quiz_attempts (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    quiz_id INTEGER NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    score NUMERIC(5,2) NOT NULL CHECK (score >= 0 AND score <= 100),
    passed BOOLEAN NOT NULL,
    attempt_number INTEGER NOT NULL CHECK (attempt_number > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (student_id, quiz_id, attempt_number)
);

CREATE TABLE IF NOT EXISTS quiz_answers (
    id SERIAL PRIMARY KEY,
    attempt_id INTEGER NOT NULL REFERENCES quiz_attempts(id) ON DELETE CASCADE,
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    selected_answer TEXT,
    is_correct BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (attempt_id, question_id)
);

CREATE TABLE IF NOT EXISTS tutor_sessions (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    attempt_id INTEGER REFERENCES quiz_attempts(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tutor_messages (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES tutor_sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('USER', 'ASSISTANT')),
    content TEXT NOT NULL CHECK (length(trim(content)) > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(50) PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Validate user roles for ownership/student-facing records.
CREATE OR REPLACE FUNCTION validate_course_instructor_role()
RETURNS TRIGGER AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM users
        WHERE id = NEW.instructor_id AND role IN ('INSTRUCTOR', 'ADMIN')
    ) THEN
        RAISE EXCEPTION 'course instructor_id must belong to an INSTRUCTOR or ADMIN';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_validate_course_instructor_role ON courses;
CREATE TRIGGER trg_validate_course_instructor_role
BEFORE INSERT OR UPDATE OF instructor_id ON courses
FOR EACH ROW EXECUTE FUNCTION validate_course_instructor_role();

CREATE OR REPLACE FUNCTION validate_student_role()
RETURNS TRIGGER AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM users
        WHERE id = NEW.student_id AND role = 'STUDENT'
    ) THEN
        RAISE EXCEPTION 'student_id must belong to a STUDENT';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_validate_enrollment_student_role ON enrollments;
CREATE TRIGGER trg_validate_enrollment_student_role
BEFORE INSERT OR UPDATE OF student_id ON enrollments
FOR EACH ROW EXECUTE FUNCTION validate_student_role();

DROP TRIGGER IF EXISTS trg_validate_lesson_progress_student_role ON lesson_progress;
CREATE TRIGGER trg_validate_lesson_progress_student_role
BEFORE INSERT OR UPDATE OF student_id ON lesson_progress
FOR EACH ROW EXECUTE FUNCTION validate_student_role();

DROP TRIGGER IF EXISTS trg_validate_quiz_attempt_student_role ON quiz_attempts;
CREATE TRIGGER trg_validate_quiz_attempt_student_role
BEFORE INSERT OR UPDATE OF student_id ON quiz_attempts
FOR EACH ROW EXECUTE FUNCTION validate_student_role();

DROP TRIGGER IF EXISTS trg_validate_tutor_session_student_role ON tutor_sessions;
CREATE TRIGGER trg_validate_tutor_session_student_role
BEFORE INSERT OR UPDATE OF student_id ON tutor_sessions
FOR EACH ROW EXECUTE FUNCTION validate_student_role();

-- Ensure a tutor session's quiz attempt belongs to the same student and section as its lesson.
CREATE OR REPLACE FUNCTION validate_tutor_session_consistency()
RETURNS TRIGGER AS $$
DECLARE
    lesson_section_id INTEGER;
    attempt_student_id INTEGER;
    quiz_section_id INTEGER;
BEGIN
    IF NEW.attempt_id IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT section_id INTO lesson_section_id
    FROM lessons WHERE id = NEW.lesson_id;

    SELECT qa.student_id, q.section_id
    INTO attempt_student_id, quiz_section_id
    FROM quiz_attempts qa
    JOIN quizzes q ON q.id = qa.quiz_id
    WHERE qa.id = NEW.attempt_id;

    IF attempt_student_id IS NULL THEN
        RAISE EXCEPTION 'attempt_id does not reference a valid quiz attempt';
    END IF;

    IF attempt_student_id <> NEW.student_id THEN
        RAISE EXCEPTION 'tutor session student_id must match quiz attempt student_id';
    END IF;

    IF lesson_section_id IS DISTINCT FROM quiz_section_id THEN
        RAISE EXCEPTION 'tutor session lesson and quiz attempt must belong to the same section';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_validate_tutor_session_consistency ON tutor_sessions;
CREATE TRIGGER trg_validate_tutor_session_consistency
BEFORE INSERT OR UPDATE OF student_id, lesson_id, attempt_id ON tutor_sessions
FOR EACH ROW EXECUTE FUNCTION validate_tutor_session_consistency();

CREATE INDEX IF NOT EXISTS idx_courses_instructor_id ON courses(instructor_id);
CREATE INDEX IF NOT EXISTS idx_sections_course_id ON sections(course_id);
CREATE INDEX IF NOT EXISTS idx_lessons_section_id ON lessons(section_id);
CREATE INDEX IF NOT EXISTS idx_flashcards_lesson_id ON flashcards(lesson_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_course_id ON enrollments(course_id);
CREATE INDEX IF NOT EXISTS idx_lesson_progress_student_id ON lesson_progress(student_id);
CREATE INDEX IF NOT EXISTS idx_quiz_attempts_student_quiz ON quiz_attempts(student_id, quiz_id);
CREATE INDEX IF NOT EXISTS idx_quiz_answers_attempt_id ON quiz_answers(attempt_id);
CREATE INDEX IF NOT EXISTS idx_tutor_sessions_student_id ON tutor_sessions(student_id);
CREATE INDEX IF NOT EXISTS idx_tutor_messages_session_id ON tutor_messages(session_id);

INSERT INTO schema_migrations (version, description)
VALUES ('0001', 'Create LearnCloud core schema')
ON CONFLICT (version) DO NOTHING;

INSERT INTO schema_migrations (version, description)
VALUES ('0002', 'Add flashcards, approval state, role and tutor-session integrity checks')
ON CONFLICT (version) DO NOTHING;

COMMIT;
