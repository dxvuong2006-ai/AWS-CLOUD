-- K4 + K5 full E2E fixture 4. INSERT-only, test database only.
-- Replace __VIDEO_SIZE_BYTES__ with the copied Lesson 4 object's exact byte size.

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
    IF pg_catalog.to_regclass('public.lessons') IS NULL
       OR pg_catalog.to_regclass('public.video_uploads') IS NULL
       OR pg_catalog.to_regclass('public.video_pipeline_runs') IS NULL
       OR pg_catalog.to_regclass('public.schema_migrations') IS NULL
       OR NOT EXISTS (
           SELECT 1 FROM public.schema_migrations WHERE version = '0005'
       ) THEN
        RAISE EXCEPTION 'K5_E2E_SCHEMA_GUARD';
    END IF;
    IF NOT EXISTS (
        SELECT 1
        FROM public.lessons l
        JOIN public.video_pipeline_runs r ON r.lesson_id = l.id
        WHERE l.id = 3
          AND l.status = 'FAILED'
          AND r.id = '158087c71b268297dfb20dfb02254b3dd6b34d9627bd092459655f552536e409'
          AND r.state = 'FAILED'
    ) THEN
        RAISE EXCEPTION 'Lesson 3 failure evidence is missing or changed';
    END IF;
    IF EXISTS (SELECT 1 FROM public.lessons WHERE id = 4)
       OR NOT EXISTS (
           SELECT 1 FROM public.lessons_id_seq
           WHERE last_value = 3 AND is_called
       ) THEN
        RAISE EXCEPTION 'Lesson ID 4 is not safely available';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.users
        WHERE cognito_sub = 'k4-k5-e2e4-instructor'
           OR email = 'k4-k5-e2e4-instructor@example.invalid'
    ) OR EXISTS (
        SELECT 1 FROM public.video_uploads
        WHERE id = '00000000000000000000000000000004'
           OR source_key = 'lessons/4/raw/00000000000000000000000000000004.mp4'
    ) OR EXISTS (
        SELECT 1 FROM public.video_pipeline_runs
        WHERE id = '65dcd70eecb600ef0ff1ec0dd3bc35c5b4444cea5668d9fd8594d689ce58eee6'
           OR output_key = 'lessons/4/processed/00000000000000000000000000000004/attempt-1/video_720p.mp4'
    ) THEN
        RAISE EXCEPTION 'K4/K5 E2E fixture 4 already exists or conflicts';
    END IF;
END;
$guard$;

WITH instructor AS (
    INSERT INTO public.users (cognito_sub, name, email, role)
    VALUES (
        'k4-k5-e2e4-instructor', 'K4 K5 E2E 4 Instructor',
        'k4-k5-e2e4-instructor@example.invalid', 'INSTRUCTOR'
    )
    RETURNING id
), course AS (
    INSERT INTO public.courses (
        instructor_id, title, description, learning_objectives, status
    )
    SELECT id, 'K4 K5 Full E2E Test 4',
           'Synthetic isolated AWS E2E fixture using the Python in 2 Minutes video',
           '["Verify K4 to K5 automatic orchestration"]'::jsonb, 'DRAFT'
    FROM instructor
    RETURNING id
), section AS (
    INSERT INTO public.sections (course_id, title, position)
    SELECT id, 'Automatic Pipeline', 1 FROM course
    RETURNING id
), lesson AS (
    INSERT INTO public.lessons (section_id, title, position, status, retry_count)
    SELECT id, 'Python in 2 Minutes - K4 K5 E2E 4', 1, 'DRAFT', 0
    FROM section
    RETURNING id
), checked_lesson AS (
    SELECT id FROM lesson WHERE id = 4
)
INSERT INTO public.video_uploads (
    id, lesson_id, source_key, content_type, size_bytes, expires_at
)
SELECT
    '00000000000000000000000000000004', id,
    'lessons/4/raw/00000000000000000000000000000004.mp4',
    'video/mp4', __VIDEO_SIZE_BYTES__, pg_catalog.now() + interval '24 hours'
FROM checked_lesson;

DO $verify$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM public.lessons l
        JOIN public.video_uploads u ON u.lesson_id = l.id
        WHERE l.id = 4 AND l.status = 'DRAFT' AND l.retry_count = 0
          AND l.raw_video_key IS NULL AND l.processed_video_key IS NULL
          AND u.id = '00000000000000000000000000000004'
          AND u.source_key = 'lessons/4/raw/00000000000000000000000000000004.mp4'
          AND u.content_type = 'video/mp4' AND u.size_bytes = __VIDEO_SIZE_BYTES__
    ) OR EXISTS (
        SELECT 1 FROM public.video_pipeline_runs
        WHERE upload_id = '00000000000000000000000000000004'
    ) THEN
        RAISE EXCEPTION 'K4/K5 E2E fixture 4 contract failed';
    END IF;
END;
$verify$;

COMMIT;

SELECT 4 AS lesson_id,
       '00000000000000000000000000000004' AS upload_id,
       '65dcd70eecb600ef0ff1ec0dd3bc35c5b4444cea5668d9fd8594d689ce58eee6' AS expected_run_id,
       'lessons/4/raw/00000000000000000000000000000004.mp4' AS raw_s3_key,
       'lessons/4/processed/00000000000000000000000000000004/attempt-1/video_720p.mp4' AS expected_output_key,
       'ai-transcripts/65dcd70eecb600ef0ff1ec0dd3bc35c5b4444cea5668d9fd8594d689ce58eee6/transcript.json' AS expected_transcript_key;
