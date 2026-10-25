CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    cognito_sub VARCHAR(255) UNIQUE,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'STUDENT',
    password_hash VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_users_role
        CHECK (role IN ('STUDENT', 'INSTRUCTOR', 'ADMIN'))
);

CREATE TABLE IF NOT EXISTS courses (
    id SERIAL PRIMARY KEY,
    instructor_id INTEGER NOT NULL REFERENCES users(id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    learning_objectives JSONB,
    status VARCHAR(20) NOT NULL DEFAULT 'DRAFT',

    CONSTRAINT chk_courses_status
        CHECK (status IN ('DRAFT', 'PUBLISHED'))
);

CREATE TABLE IF NOT EXISTS sections (
    id SERIAL PRIMARY KEY,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    position INTEGER NOT NULL,

    CONSTRAINT uq_sections_course_position UNIQUE (course_id, position),
    CONSTRAINT chk_sections_position_positive CHECK (position > 0)
);

CREATE TABLE IF NOT EXISTS lessons (
    id SERIAL PRIMARY KEY,
    section_id INTEGER NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    position INTEGER NOT NULL,
    raw_video_key VARCHAR(512),
    processed_video_key VARCHAR(512),
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT',
    transcript_json JSONB,
    summary TEXT,
    key_concepts_json JSONB,

    CONSTRAINT chk_lessons_position_positive CHECK (position > 0)
);

CREATE TABLE IF NOT EXISTS enrollments (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    enrolled_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (student_id, course_id)
);
