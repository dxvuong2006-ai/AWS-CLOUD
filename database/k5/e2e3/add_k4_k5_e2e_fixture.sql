-- K4 + K5 full E2E fixture 3. INSERT-only, test database only.
-- Before running in pgAdmin, replace __VIDEO_SIZE_BYTES__ with the exact MP4 byte size.

BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';
SET LOCAL search_path = pg_catalog, public;

DO $guard$
BEGIN
    IF current_database() <> 'learncloud_k5_test'
       OR current_user <> 'learncloud_k5_test_user' THEN
        RAISE EXCEPTION 'K5_E2E_DATABASE_GUARD';
    END IF;
    IF (
        SELECT pg_catalog.pg_get_userbyid(datdba)
        FROM pg_catalog.pg_database
        WHERE datname = pg_catalog.current_database()
    ) <> 'learncloud_k5_test_user' THEN
        RAISE EXCEPTION 'K5_E2E_OWNER_GUARD';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM public.schema_migrations WHERE version = '0005'
    ) THEN
        RAISE EXCEPTION 'K5_E2E_SCHEMA_GUARD';
    END IF;
    IF EXISTS (SELECT 1 FROM public.lessons WHERE id = 3)
       OR NOT EXISTS (
           SELECT 1 FROM public.lessons_id_seq
           WHERE last_value = 2 AND is_called
       ) THEN
        RAISE EXCEPTION 'Lesson ID 3 is not safely available';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.video_uploads
        WHERE id = '00000000000000000000000000000003'
           OR source_key = 'lessons/3/raw/00000000000000000000000000000003.mp4'
    ) OR EXISTS (
        SELECT 1 FROM public.video_pipeline_runs
        WHERE id = '158087c71b268297dfb20dfb02254b3dd6b34d9627bd092459655f552536e409'
    ) THEN
        RAISE EXCEPTION 'K4/K5 E2E fixture 3 already exists';
    END IF;
END;
$guard$;

WITH instructor AS (
    INSERT INTO public.users (cognito_sub, name, email, role)
    VALUES (
        'k4-k5-e2e3-instructor', 'K4 K5 E2E 3 Instructor',
        'k4-k5-e2e3-instructor@example.invalid', 'INSTRUCTOR'
    )
    RETURNING id
), course AS (
    INSERT INTO public.courses (
        instructor_id, title, description, learning_objectives, status
    )
    SELECT id, 'K4 K5 Full E2E Test 3', 'Synthetic isolated AWS E2E fixture',
           '["Verify K4 to K5 automatic orchestration"]'::jsonb, 'DRAFT'
    FROM instructor
    RETURNING id
), section AS (
    INSERT INTO public.sections (course_id, title, position)
    SELECT id, 'Automatic Pipeline', 1 FROM course
    RETURNING id
), lesson AS (
    INSERT INTO public.lessons (section_id, title, position, status, retry_count)
    SELECT id, 'K4 K5 Automatic E2E', 1, 'DRAFT', 0
    FROM section
    RETURNING id
), checked_lesson AS (
    SELECT id FROM lesson WHERE id = 3
)
INSERT INTO public.video_uploads (
    id, lesson_id, source_key, content_type, size_bytes, expires_at
)
SELECT
    '00000000000000000000000000000003', id,
    'lessons/3/raw/00000000000000000000000000000003.mp4',
    'video/mp4', __VIDEO_SIZE_BYTES__, pg_catalog.now() + interval '24 hours'
FROM checked_lesson;

DO $verify$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM public.lessons l
        JOIN public.video_uploads u ON u.lesson_id = l.id
        WHERE l.id = 3 AND l.status = 'DRAFT' AND l.retry_count = 0
          AND l.raw_video_key IS NULL AND l.processed_video_key IS NULL
          AND u.id = '00000000000000000000000000000003'
          AND u.source_key = 'lessons/3/raw/00000000000000000000000000000003.mp4'
          AND u.content_type = 'video/mp4' AND u.size_bytes = __VIDEO_SIZE_BYTES__
    ) OR EXISTS (
        SELECT 1 FROM public.video_pipeline_runs
        WHERE upload_id = '00000000000000000000000000000003'
    ) THEN
        RAISE EXCEPTION 'K4/K5 E2E fixture 3 contract failed';
    END IF;
END;
$verify$;

COMMIT;

SELECT 3 AS lesson_id,
       '00000000000000000000000000000003' AS upload_id,
       '158087c71b268297dfb20dfb02254b3dd6b34d9627bd092459655f552536e409' AS expected_run_id,
       'lessons/3/raw/00000000000000000000000000000003.mp4' AS raw_s3_key,
       'lessons/3/processed/00000000000000000000000000000003/attempt-1/video_720p.mp4' AS expected_output_key;
