-- LearnCloud K4/K5 isolated PostgreSQL 16 bootstrap.
-- Target database: learncloud_k5_test
-- Target owner/login: learncloud_k5_test_user
--
-- Fresh database only. This script intentionally contains no DROP or TRUNCATE.
-- Run while connected to learncloud_k5_test as learncloud_k5_test_user.

BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';
SET LOCAL search_path = pg_catalog, public;

DO $guard$
BEGIN
    IF current_database() <> 'learncloud_k5_test' THEN
        RAISE EXCEPTION 'Refusing database %, expected learncloud_k5_test', current_database();
    END IF;
    IF current_user <> 'learncloud_k5_test_user' THEN
        RAISE EXCEPTION 'Refusing role %, expected learncloud_k5_test_user', current_user;
    END IF;
    IF (
        SELECT pg_catalog.pg_get_userbyid(d.datdba)
        FROM pg_catalog.pg_database d
        WHERE d.datname = pg_catalog.current_database()
    ) <> 'learncloud_k5_test_user' THEN
        RAISE EXCEPTION 'Database owner must be learncloud_k5_test_user';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind IN ('r', 'p')
          AND c.relname IN ('users', 'courses', 'lessons', 'video_pipeline_runs')
    ) THEN
        RAISE EXCEPTION 'Core LearnCloud tables already exist; this bootstrap is fresh-database only';
    END IF;
END;
$guard$;

CREATE TABLE public.schema_migrations (
    version VARCHAR(50) PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.now()
);

CREATE TABLE public.users (
    id SERIAL PRIMARY KEY,
    cognito_sub VARCHAR(255),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(320) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'STUDENT',
    password_hash VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.now(),
    CONSTRAINT uq_users_cognito_sub UNIQUE (cognito_sub),
    CONSTRAINT uq_users_email UNIQUE (email),
    CONSTRAINT ck_users_role CHECK (role IN ('STUDENT', 'INSTRUCTOR', 'ADMIN'))
);

CREATE TABLE public.courses (
    id SERIAL PRIMARY KEY,
    instructor_id INTEGER NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    cover_image TEXT,
    learning_objectives JSONB NOT NULL DEFAULT '[]'::jsonb,
    status VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.now(),
    CONSTRAINT fk_courses_instructor FOREIGN KEY (instructor_id)
        REFERENCES public.users(id) ON DELETE RESTRICT,
    CONSTRAINT ck_courses_learning_objectives_array
        CHECK (pg_catalog.jsonb_typeof(learning_objectives) = 'array'),
    CONSTRAINT ck_courses_status CHECK (status IN ('DRAFT', 'PUBLISHED'))
);

CREATE TABLE public.sections (
    id SERIAL PRIMARY KEY,
    course_id INTEGER NOT NULL,
    title VARCHAR(255) NOT NULL,
    position INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.now(),
    update_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.now(),
    CONSTRAINT fk_sections_course FOREIGN KEY (course_id)
        REFERENCES public.courses(id) ON DELETE CASCADE,
    CONSTRAINT ck_sections_position CHECK (position > 0),
    CONSTRAINT uq_sections_course_position UNIQUE (course_id, position)
);

CREATE TABLE public.lessons (
    id SERIAL PRIMARY KEY,
    section_id INTEGER NOT NULL,
    title VARCHAR(255) NOT NULL,
    position INTEGER NOT NULL,
    raw_video_key TEXT,
    processed_video_key TEXT,
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT',
    transcript_json JSONB,
    summary TEXT,
    key_concepts_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    duration_seconds INTEGER,
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.now(),
    CONSTRAINT fk_lessons_section FOREIGN KEY (section_id)
        REFERENCES public.sections(id) ON DELETE CASCADE,
    CONSTRAINT ck_lessons_position CHECK (position > 0),
    CONSTRAINT ck_lessons_status CHECK (status IN (
        'DRAFT', 'UPLOADED', 'PROCESSING', 'TRANSCRIBING',
        'AI_PROCESSING', 'REVIEW_REQUIRED', 'PUBLISHED', 'FAILED'
    )),
    CONSTRAINT ck_lessons_key_concepts_array
        CHECK (pg_catalog.jsonb_typeof(key_concepts_json) = 'array'),
    CONSTRAINT ck_lessons_duration_seconds
        CHECK (duration_seconds IS NULL OR duration_seconds >= 0),
    CONSTRAINT ck_lessons_retry_count CHECK (retry_count >= 0),
    CONSTRAINT uq_lessons_section_position UNIQUE (section_id, position)
);

CREATE TABLE public.flashcards (
    id SERIAL PRIMARY KEY,
    lesson_id INTEGER NOT NULL,
    front TEXT NOT NULL,
    back TEXT NOT NULL,
    position INTEGER NOT NULL,
    is_approved BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.now(),
    CONSTRAINT fk_flashcards_lesson FOREIGN KEY (lesson_id)
        REFERENCES public.lessons(id) ON DELETE CASCADE,
    CONSTRAINT ck_flashcards_front_not_blank CHECK (length(pg_catalog.btrim(front)) > 0),
    CONSTRAINT ck_flashcards_back_not_blank CHECK (length(pg_catalog.btrim(back)) > 0),
    CONSTRAINT ck_flashcards_position CHECK (position > 0),
    CONSTRAINT uq_flashcards_lesson_position UNIQUE (lesson_id, position)
);

CREATE TABLE public.enrollments (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    enrolled_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.now(),
    CONSTRAINT fk_enrollments_student FOREIGN KEY (student_id)
        REFERENCES public.users(id) ON DELETE CASCADE,
    CONSTRAINT fk_enrollments_course FOREIGN KEY (course_id)
        REFERENCES public.courses(id) ON DELETE CASCADE,
    CONSTRAINT uq_enrollments_student_course UNIQUE (student_id, course_id)
);

CREATE TABLE public.lesson_progress (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL,
    lesson_id INTEGER NOT NULL,
    watched_seconds INTEGER NOT NULL DEFAULT 0,
    completed BOOLEAN NOT NULL DEFAULT false,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.now(),
    CONSTRAINT fk_lesson_progress_student FOREIGN KEY (student_id)
        REFERENCES public.users(id) ON DELETE CASCADE,
    CONSTRAINT fk_lesson_progress_lesson FOREIGN KEY (lesson_id)
        REFERENCES public.lessons(id) ON DELETE CASCADE,
    CONSTRAINT ck_lesson_progress_watched_seconds CHECK (watched_seconds >= 0),
    CONSTRAINT uq_lesson_progress_student_lesson UNIQUE (student_id, lesson_id)
);

CREATE TABLE public.quizzes (
    id SERIAL PRIMARY KEY,
    section_id INTEGER NOT NULL,
    title VARCHAR(255) NOT NULL,
    passing_score NUMERIC(5,2) NOT NULL DEFAULT 80.00,
    is_approved BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.now(),
    CONSTRAINT fk_quizzes_section FOREIGN KEY (section_id)
        REFERENCES public.sections(id) ON DELETE CASCADE,
    CONSTRAINT uq_quizzes_section UNIQUE (section_id),
    CONSTRAINT ck_quizzes_passing_score CHECK (passing_score BETWEEN 0 AND 100)
);

CREATE TABLE public.questions (
    id SERIAL PRIMARY KEY,
    quiz_id INTEGER NOT NULL,
    question TEXT NOT NULL,
    options_json JSONB NOT NULL,
    correct_answer TEXT NOT NULL,
    explanation TEXT,
    topic VARCHAR(255),
    source_start_seconds NUMERIC(10,3),
    source_end_seconds NUMERIC(10,3),
    position INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.now(),
    CONSTRAINT fk_questions_quiz FOREIGN KEY (quiz_id)
        REFERENCES public.quizzes(id) ON DELETE CASCADE,
    CONSTRAINT ck_questions_not_blank CHECK (length(pg_catalog.btrim(question)) > 0),
    CONSTRAINT ck_questions_options_array CHECK (
        pg_catalog.jsonb_typeof(options_json) = 'array'
        AND pg_catalog.jsonb_array_length(options_json) >= 2
    ),
    CONSTRAINT ck_questions_correct_answer_in_options CHECK (options_json ? correct_answer),
    CONSTRAINT ck_questions_source_range CHECK (
        (source_start_seconds IS NULL AND source_end_seconds IS NULL)
        OR (source_start_seconds IS NOT NULL AND source_end_seconds IS NOT NULL
            AND source_start_seconds >= 0
            AND source_end_seconds >= source_start_seconds)
    ),
    CONSTRAINT ck_questions_position CHECK (position > 0),
    CONSTRAINT uq_questions_quiz_position UNIQUE (quiz_id, position)
);

CREATE TABLE public.quiz_attempts (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL,
    quiz_id INTEGER NOT NULL,
    score NUMERIC(5,2) NOT NULL,
    passed BOOLEAN NOT NULL,
    attempt_number INTEGER NOT NULL,
    request_id VARCHAR(36),
    request_hash VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.now(),
    CONSTRAINT fk_quiz_attempts_student FOREIGN KEY (student_id)
        REFERENCES public.users(id) ON DELETE CASCADE,
    CONSTRAINT fk_quiz_attempts_quiz FOREIGN KEY (quiz_id)
        REFERENCES public.quizzes(id) ON DELETE CASCADE,
    CONSTRAINT ck_quiz_attempts_score CHECK (score BETWEEN 0 AND 100),
    CONSTRAINT ck_quiz_attempts_number CHECK (attempt_number > 0),
    CONSTRAINT uq_quiz_attempts_student_quiz_number
        UNIQUE (student_id, quiz_id, attempt_number),
    CONSTRAINT uq_quiz_attempts_request UNIQUE (student_id, quiz_id, request_id)
);

CREATE TABLE public.quiz_answers (
    id SERIAL PRIMARY KEY,
    attempt_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    selected_answer TEXT,
    is_correct BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.now(),
    CONSTRAINT fk_quiz_answers_attempt FOREIGN KEY (attempt_id)
        REFERENCES public.quiz_attempts(id) ON DELETE CASCADE,
    CONSTRAINT fk_quiz_answers_question FOREIGN KEY (question_id)
        REFERENCES public.questions(id) ON DELETE CASCADE,
    CONSTRAINT uq_quiz_answers_attempt_question UNIQUE (attempt_id, question_id)
);

CREATE TABLE public.checkpoint_remediation (
    attempt_id INTEGER PRIMARY KEY,
    explanation_completed BOOLEAN NOT NULL DEFAULT false,
    review_completed BOOLEAN NOT NULL DEFAULT false,
    practice_total INTEGER NOT NULL DEFAULT 0,
    practice_correct INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.now(),
    CONSTRAINT fk_checkpoint_remediation_attempt FOREIGN KEY (attempt_id)
        REFERENCES public.quiz_attempts(id) ON DELETE CASCADE,
    CONSTRAINT ck_checkpoint_remediation_total CHECK (practice_total BETWEEN 0 AND 3),
    CONSTRAINT ck_checkpoint_remediation_correct CHECK (
        practice_correct >= 0 AND practice_correct <= practice_total
    )
);

CREATE TABLE public.tutor_sessions (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL,
    lesson_id INTEGER NOT NULL,
    attempt_id INTEGER,
    practice_questions JSONB NOT NULL DEFAULT '[]'::jsonb,
    remediation_completed BOOLEAN NOT NULL DEFAULT false,
    workflow_state JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.now(),
    CONSTRAINT fk_tutor_sessions_student FOREIGN KEY (student_id)
        REFERENCES public.users(id) ON DELETE CASCADE,
    CONSTRAINT fk_tutor_sessions_lesson FOREIGN KEY (lesson_id)
        REFERENCES public.lessons(id) ON DELETE CASCADE,
    CONSTRAINT fk_tutor_sessions_attempt FOREIGN KEY (attempt_id)
        REFERENCES public.quiz_attempts(id) ON DELETE SET NULL,
    CONSTRAINT ck_tutor_sessions_practice_questions_array
        CHECK (pg_catalog.jsonb_typeof(practice_questions) = 'array')
);

CREATE TABLE public.tutor_messages (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.now(),
    CONSTRAINT fk_tutor_messages_session FOREIGN KEY (session_id)
        REFERENCES public.tutor_sessions(id) ON DELETE CASCADE,
    CONSTRAINT ck_tutor_messages_role CHECK (role IN ('USER', 'ASSISTANT')),
    CONSTRAINT ck_tutor_messages_content_not_blank
        CHECK (length(pg_catalog.btrim(content)) > 0)
);

CREATE TABLE public.video_uploads (
    id VARCHAR(32) PRIMARY KEY,
    lesson_id INTEGER NOT NULL,
    source_key TEXT NOT NULL,
    content_type VARCHAR(64) NOT NULL,
    size_bytes INTEGER NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.now(),
    CONSTRAINT fk_video_uploads_lesson FOREIGN KEY (lesson_id)
        REFERENCES public.lessons(id),
    CONSTRAINT uq_video_uploads_source_key UNIQUE (source_key),
    CONSTRAINT uq_video_upload_id_lesson UNIQUE (id, lesson_id),
    CONSTRAINT ck_video_upload_size CHECK (size_bytes > 0 AND size_bytes <= 524288000)
);

CREATE TABLE public.video_pipeline_runs (
    id VARCHAR(64) PRIMARY KEY,
    upload_id VARCHAR(32) NOT NULL,
    lesson_id INTEGER NOT NULL,
    attempt INTEGER NOT NULL,
    state VARCHAR(24) NOT NULL,
    execution_arn TEXT,
    source_etag VARCHAR(128) NOT NULL,
    output_key TEXT NOT NULL,
    job_id VARCHAR(128),
    error_code VARCHAR(64),
    safe_to_retry BOOLEAN NOT NULL DEFAULT false,
    next_dispatch_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.now(),
    CONSTRAINT fk_video_pipeline_runs_lesson FOREIGN KEY (lesson_id)
        REFERENCES public.lessons(id),
    CONSTRAINT fk_video_run_upload_lesson FOREIGN KEY (upload_id, lesson_id)
        REFERENCES public.video_uploads(id, lesson_id),
    CONSTRAINT uq_video_run_upload_attempt UNIQUE (upload_id, attempt),
    CONSTRAINT uq_video_pipeline_runs_execution_arn UNIQUE (execution_arn),
    CONSTRAINT ck_video_run_attempt CHECK (attempt >= 0),
    CONSTRAINT ck_video_run_state CHECK (state IN (
        'QUEUED', 'CLAIMED', 'SUBMITTING', 'TRANSCODING',
        'VIDEO_READY', 'COMPLETE', 'FAILED'
    ))
);

CREATE TABLE public.local_auth_identities (
    user_id INTEGER PRIMARY KEY,
    verified_at TIMESTAMPTZ,
    login_failures INTEGER NOT NULL DEFAULT 0,
    locked_until TIMESTAMPTZ,
    provisioned_at TIMESTAMPTZ,
    provisioned_by VARCHAR(63),
    provisioning_reference VARCHAR(128),
    CONSTRAINT fk_local_auth_identities_user FOREIGN KEY (user_id)
        REFERENCES public.users(id) ON DELETE CASCADE,
    CONSTRAINT ck_local_auth_identities_login_failures CHECK (login_failures >= 0),
    CONSTRAINT ck_local_identity_provisioning CHECK (
        (provisioned_at IS NULL AND provisioned_by IS NULL AND provisioning_reference IS NULL)
        OR (provisioned_at IS NOT NULL AND provisioned_by IS NOT NULL
            AND provisioning_reference IS NOT NULL AND verified_at IS NOT NULL
            AND length(pg_catalog.btrim(provisioned_by)) > 0
            AND length(pg_catalog.btrim(provisioning_reference)) > 0)
    )
);

CREATE TABLE public.local_auth_otps (
    user_id INTEGER NOT NULL,
    purpose VARCHAR(10) NOT NULL,
    code_hash VARCHAR(64) NOT NULL,
    nonce VARCHAR(64) NOT NULL,
    sent_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    consumed_at TIMESTAMPTZ,
    CONSTRAINT pk_local_auth_otps PRIMARY KEY (user_id, purpose),
    CONSTRAINT fk_local_auth_otps_user FOREIGN KEY (user_id)
        REFERENCES public.users(id) ON DELETE CASCADE,
    CONSTRAINT ck_local_otp_purpose CHECK (purpose IN ('verify', 'reset')),
    CONSTRAINT ck_local_auth_otps_attempts CHECK (attempts >= 0)
);

CREATE TABLE public.local_auth_sessions (
    token_hash VARCHAR(64) PRIMARY KEY,
    user_id INTEGER NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    CONSTRAINT fk_local_auth_sessions_user FOREIGN KEY (user_id)
        REFERENCES public.users(id) ON DELETE CASCADE
);

CREATE OR REPLACE FUNCTION public.validate_course_instructor_role()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $function$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM public.users
        WHERE id = NEW.instructor_id AND role IN ('INSTRUCTOR', 'ADMIN')
    ) THEN
        RAISE EXCEPTION 'course instructor_id must belong to an INSTRUCTOR or ADMIN';
    END IF;
    RETURN NEW;
END;
$function$;

CREATE TRIGGER trg_validate_course_instructor_role
BEFORE INSERT OR UPDATE OF instructor_id ON public.courses
FOR EACH ROW EXECUTE FUNCTION public.validate_course_instructor_role();

CREATE OR REPLACE FUNCTION public.validate_student_role()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $function$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM public.users WHERE id = NEW.student_id AND role = 'STUDENT'
    ) THEN
        RAISE EXCEPTION 'student_id must belong to a STUDENT';
    END IF;
    RETURN NEW;
END;
$function$;

CREATE TRIGGER trg_validate_enrollment_student_role
BEFORE INSERT OR UPDATE OF student_id ON public.enrollments
FOR EACH ROW EXECUTE FUNCTION public.validate_student_role();

CREATE TRIGGER trg_validate_lesson_progress_student_role
BEFORE INSERT OR UPDATE OF student_id ON public.lesson_progress
FOR EACH ROW EXECUTE FUNCTION public.validate_student_role();

CREATE TRIGGER trg_validate_quiz_attempt_student_role
BEFORE INSERT OR UPDATE OF student_id ON public.quiz_attempts
FOR EACH ROW EXECUTE FUNCTION public.validate_student_role();

CREATE TRIGGER trg_validate_tutor_session_student_role
BEFORE INSERT OR UPDATE OF student_id ON public.tutor_sessions
FOR EACH ROW EXECUTE FUNCTION public.validate_student_role();

CREATE OR REPLACE FUNCTION public.validate_tutor_session_consistency()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $function$
DECLARE
    lesson_section_id INTEGER;
    attempt_student_id INTEGER;
    quiz_section_id INTEGER;
BEGIN
    IF NEW.attempt_id IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT section_id INTO lesson_section_id
    FROM public.lessons WHERE id = NEW.lesson_id;

    SELECT qa.student_id, q.section_id
    INTO attempt_student_id, quiz_section_id
    FROM public.quiz_attempts qa
    JOIN public.quizzes q ON q.id = qa.quiz_id
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
$function$;

CREATE TRIGGER trg_validate_tutor_session_consistency
BEFORE INSERT OR UPDATE OF student_id, lesson_id, attempt_id ON public.tutor_sessions
FOR EACH ROW EXECUTE FUNCTION public.validate_tutor_session_consistency();

CREATE INDEX idx_courses_instructor_id ON public.courses(instructor_id);
CREATE INDEX idx_sections_course_id ON public.sections(course_id);
CREATE INDEX idx_lessons_section_id ON public.lessons(section_id);
CREATE INDEX idx_flashcards_lesson_id ON public.flashcards(lesson_id);
CREATE INDEX idx_enrollments_course_id ON public.enrollments(course_id);
CREATE INDEX idx_lesson_progress_student_id ON public.lesson_progress(student_id);
CREATE INDEX idx_quiz_attempts_student_quiz ON public.quiz_attempts(student_id, quiz_id);
CREATE INDEX idx_quiz_answers_attempt_id ON public.quiz_answers(attempt_id);
CREATE INDEX idx_tutor_sessions_student_id ON public.tutor_sessions(student_id);
CREATE INDEX idx_tutor_messages_session_id ON public.tutor_messages(session_id);
CREATE INDEX ix_video_uploads_lesson_id ON public.video_uploads(lesson_id);
CREATE INDEX ix_video_pipeline_runs_lesson_id ON public.video_pipeline_runs(lesson_id);
CREATE INDEX ix_video_pipeline_outbox ON public.video_pipeline_runs(next_dispatch_at)
    WHERE state = 'QUEUED';
CREATE INDEX ix_local_auth_sessions_user_id ON public.local_auth_sessions(user_id);
CREATE INDEX ix_local_auth_sessions_expires_at ON public.local_auth_sessions(expires_at);

INSERT INTO public.schema_migrations (version, description) VALUES
    ('0001', 'Create LearnCloud core schema'),
    ('0002', 'Add flashcards, approval state, role and tutor-session integrity checks'),
    ('0003', 'Reconcile legacy schema with current backend models'),
    ('0004', 'Remove approved lesson status; publish directly after review'),
    ('0005', 'Add video upload intents and pipeline ledger with upload/lesson integrity'),
    ('0006', 'Course cover and resumable remediation workflow'),
    ('0007', 'Opt-in development/test local auth, hashed email OTP and revocable sessions'),
    ('0008', 'Explicit operator provisioning of existing local auth identities');

-- Minimal synthetic K5 E2E fixture. It contains no credentials or production data.
WITH instructor AS (
    INSERT INTO public.users (cognito_sub, name, email, role)
    VALUES ('k5-test-instructor', 'K5 Test Instructor', 'k5-instructor@example.invalid', 'INSTRUCTOR')
    RETURNING id
), course AS (
    INSERT INTO public.courses (
        instructor_id, title, description, learning_objectives, status
    )
    SELECT id, 'K5 E2E Test Course', 'Synthetic local-only K5 fixture',
           '["Validate K4/K5 persistence"]'::jsonb, 'DRAFT'
    FROM instructor
    RETURNING id
), section AS (
    INSERT INTO public.sections (course_id, title, position)
    SELECT id, 'K5 E2E Section', 1 FROM course
    RETURNING id
), lesson AS (
    INSERT INTO public.lessons (
        section_id, title, position, raw_video_key, processed_video_key,
        status, retry_count
    )
    SELECT id, 'K5 E2E Lesson', 1,
           'lessons/k5-test/raw/00000000000000000000000000000001.mp4',
           'lessons/k5-test/processed/00000000000000000000000000000001/attempt-0/video_720p.mp4',
           'PROCESSING', 0
    FROM section
    RETURNING id
), upload AS (
    INSERT INTO public.video_uploads (
        id, lesson_id, source_key, content_type, size_bytes, expires_at
    )
    SELECT '00000000000000000000000000000001', id,
           'lessons/k5-test/raw/00000000000000000000000000000001.mp4',
           'video/mp4', 1024, '2099-01-01 00:00:00+00'::timestamptz
    FROM lesson
    RETURNING id, lesson_id
)
INSERT INTO public.video_pipeline_runs (
    id, upload_id, lesson_id, attempt, state, execution_arn,
    source_etag, output_key, safe_to_retry
)
SELECT
    'cb1d51e7cf146c2547aab8ff4f11eba90718a6f9f4ae5d89198e03f47113977a',
    id, lesson_id, 0, 'VIDEO_READY',
    'arn:aws:states:ap-southeast-1:000000000000:execution:k5-local:e2e-fixture',
    'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',
    'lessons/k5-test/processed/00000000000000000000000000000001/attempt-0/video_720p.mp4',
    true
FROM upload;

DO $verify$
DECLARE
    missing_tables TEXT;
    invalid_constraints INTEGER;
BEGIN
    SELECT pg_catalog.string_agg(required.name, ', ' ORDER BY required.name)
    INTO missing_tables
    FROM (VALUES
        ('users'), ('courses'), ('sections'), ('lessons'), ('flashcards'),
        ('enrollments'), ('lesson_progress'), ('quizzes'), ('questions'),
        ('quiz_attempts'), ('quiz_answers'), ('checkpoint_remediation'),
        ('tutor_sessions'), ('tutor_messages'), ('video_uploads'),
        ('video_pipeline_runs'), ('local_auth_identities'), ('local_auth_otps'),
        ('local_auth_sessions'), ('schema_migrations')
    ) AS required(name)
    WHERE pg_catalog.to_regclass('public.' || required.name) IS NULL;

    IF missing_tables IS NOT NULL THEN
        RAISE EXCEPTION 'Missing required tables: %', missing_tables;
    END IF;

    SELECT count(*) INTO invalid_constraints
    FROM pg_catalog.pg_constraint c
    JOIN pg_catalog.pg_namespace n ON n.oid = c.connamespace
    WHERE n.nspname = 'public' AND NOT c.convalidated;

    IF invalid_constraints <> 0 THEN
        RAISE EXCEPTION 'Found % unvalidated constraints', invalid_constraints;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM public.video_pipeline_runs
        WHERE id = 'cb1d51e7cf146c2547aab8ff4f11eba90718a6f9f4ae5d89198e03f47113977a'
          AND state = 'VIDEO_READY'
    ) THEN
        RAISE EXCEPTION 'K5 E2E fixture is missing or invalid';
    END IF;
END;
$verify$;

COMMIT;
