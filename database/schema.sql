CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    cognito_sub VARCHAR(255) UNIQUE,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'STUDENT',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_users_role
        CHECK (role IN ('STUDENT', 'INSTRUCTOR', 'ADMIN'))
);

CREATE TABLE courses (
    id SERIAL PRIMARY KEY,
    instructor_id INTEGER NOT NULL REFERENCES users(id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    learning_objectives JSONB,
    status VARCHAR(20) NOT NULL DEFAULT 'DRAFT',

    CONSTRAINT chk_courses_status
        CHECK (status IN ('DRAFT', 'PUBLISHED'))
);
