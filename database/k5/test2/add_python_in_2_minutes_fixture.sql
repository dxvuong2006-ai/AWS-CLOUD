-- K5 E2E fixture 2: "Python in 2 Minutes" (English).
-- INSERT-only and intended only for learncloud_k5_test.
-- The existing fixture is read for guards but is never changed.

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
    IF pg_catalog.to_regclass('public.lessons') IS NULL
       OR pg_catalog.to_regclass('public.video_uploads') IS NULL
       OR pg_catalog.to_regclass('public.video_pipeline_runs') IS NULL
       OR pg_catalog.to_regclass('public.schema_migrations') IS NULL THEN
        RAISE EXCEPTION 'LearnCloud K5 schema is incomplete';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM public.schema_migrations WHERE version = '0005'
    ) THEN
        RAISE EXCEPTION 'Migration 0005 is required';
    END IF;
    IF NOT EXISTS (
        SELECT 1
        FROM public.video_pipeline_runs
        WHERE id = 'cb1d51e7cf146c2547aab8ff4f11eba90718a6f9f4ae5d89198e03f47113977a'
          AND lesson_id = 1
    ) THEN
        RAISE EXCEPTION 'Original K5 fixture is missing; inspect this database before adding fixture 2';
    END IF;
    IF EXISTS (SELECT 1 FROM public.lessons WHERE id = 2)
       OR NOT EXISTS (
           SELECT 1 FROM public.lessons_id_seq
           WHERE last_value = 1 AND is_called
       ) THEN
        RAISE EXCEPTION 'Lesson ID 2 is not safely available; no rows were inserted';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.video_uploads
        WHERE id = '00000000000000000000000000000002'
           OR source_key = 'lessons/2/raw/00000000000000000000000000000002.mp4'
    ) OR EXISTS (
        SELECT 1 FROM public.video_pipeline_runs
        WHERE id = '038ef54af3fd1e35aa1d23c47ea80791f82e601aad1caece9975147a194e47de'
           OR execution_arn = 'arn:aws:states:ap-southeast-1:000000000000:execution:k5-local:e2e-fixture-2'
           OR output_key = 'lessons/2/processed/00000000000000000000000000000002/attempt-0/video_720p.mp4'
    ) THEN
        RAISE EXCEPTION 'K5 fixture 2 already exists or conflicts; no rows were inserted';
    END IF;
END;
$guard$;

WITH instructor AS (
    INSERT INTO public.users (cognito_sub, name, email, role)
    VALUES (
        'k5-test2-instructor',
        'K5 Test 2 Instructor',
        'k5-test2-instructor@example.invalid',
        'INSTRUCTOR'
    )
    RETURNING id
), course AS (
    INSERT INTO public.courses (
        instructor_id, title, description, learning_objectives, status
    )
    SELECT id, 'Python in 2 Minutes', 'Synthetic local-only K5 fixture 2',
           '["Generate English learning content from a short Python video"]'::jsonb,
           'DRAFT'
    FROM instructor
    RETURNING id
), section AS (
    INSERT INTO public.sections (course_id, title, position)
    SELECT id, 'Python Basics', 1 FROM course
    RETURNING id
), lesson AS (
    INSERT INTO public.lessons (
        section_id, title, position, raw_video_key, processed_video_key,
        status, retry_count
    )
    SELECT id, 'Python in 2 Minutes', 1,
           'lessons/2/raw/00000000000000000000000000000002.mp4',
           'lessons/2/processed/00000000000000000000000000000002/attempt-0/video_720p.mp4',
           'PROCESSING', 0
    FROM section
    RETURNING id
), checked_lesson AS (
    SELECT id FROM lesson
    WHERE id = 2
), upload AS (
    INSERT INTO public.video_uploads (
        id, lesson_id, source_key, content_type, size_bytes, expires_at
    )
    SELECT '00000000000000000000000000000002', id,
           'lessons/2/raw/00000000000000000000000000000002.mp4',
           'video/mp4', 1024, '2099-01-01 00:00:00+00'::timestamptz
    FROM checked_lesson
    RETURNING id, lesson_id
)
INSERT INTO public.video_pipeline_runs (
    id, upload_id, lesson_id, attempt, state, execution_arn,
    source_etag, output_key, safe_to_retry
)
SELECT
    '038ef54af3fd1e35aa1d23c47ea80791f82e601aad1caece9975147a194e47de',
    id, lesson_id, 0, 'VIDEO_READY',
    'arn:aws:states:ap-southeast-1:000000000000:execution:k5-local:e2e-fixture-2',
    'ffffffffffffffffffffffffffffffff',
    'lessons/2/processed/00000000000000000000000000000002/attempt-0/video_720p.mp4',
    true
FROM upload;

DO $verify$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM public.video_pipeline_runs r
        JOIN public.video_uploads u
          ON u.id = r.upload_id AND u.lesson_id = r.lesson_id
        JOIN public.lessons l ON l.id = r.lesson_id
        WHERE r.id = '038ef54af3fd1e35aa1d23c47ea80791f82e601aad1caece9975147a194e47de'
          AND r.lesson_id = 2
          AND r.attempt = 0
          AND r.state = 'VIDEO_READY'
          AND r.execution_arn = 'arn:aws:states:ap-southeast-1:000000000000:execution:k5-local:e2e-fixture-2'
          AND r.output_key = l.processed_video_key
          AND u.source_key = l.raw_video_key
          AND l.status = 'PROCESSING'
          AND l.retry_count = 0
    ) THEN
        RAISE EXCEPTION 'K5 fixture 2 failed its post-insert contract check';
    END IF;
END;
$verify$;

COMMIT;

SELECT l.id AS lesson_id, r.id AS run_id, r.execution_arn,
       l.processed_video_key AS s3_video_key,
       'learncloud-k5-' || r.id AS transcribe_job_id
FROM public.video_pipeline_runs r
JOIN public.lessons l ON l.id = r.lesson_id
WHERE r.id = '038ef54af3fd1e35aa1d23c47ea80791f82e601aad1caece9975147a194e47de';
