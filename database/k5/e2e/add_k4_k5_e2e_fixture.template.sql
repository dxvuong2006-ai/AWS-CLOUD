-- Reusable K4 + K5 full E2E fixture. INSERT-only, test database only.
-- This file must be rendered completely before execution.

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
    IF EXISTS (SELECT 1 FROM public.lessons WHERE id = __LESSON_ID__)
       OR NOT EXISTS (
           SELECT 1 FROM public.lessons_id_seq
           WHERE last_value = __PREVIOUS_LESSON_ID__ AND is_called
       ) THEN
        RAISE EXCEPTION 'Requested Lesson ID is not safely available';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.users
        WHERE cognito_sub = 'k4-k5-e2e__LESSON_ID__-instructor'
           OR email = 'k4-k5-e2e__LESSON_ID__-instructor@example.invalid'
    ) OR EXISTS (
        SELECT 1 FROM public.video_uploads
        WHERE id = '__UPLOAD_ID__'
           OR source_key = 'lessons/__LESSON_ID__/raw/__UPLOAD_ID__.mp4'
    ) OR EXISTS (
        SELECT 1 FROM public.video_pipeline_runs
        WHERE id = '__RUN_ID__'
           OR output_key = 'lessons/__LESSON_ID__/processed/__UPLOAD_ID__/attempt-1/video_720p.mp4'
    ) THEN
        RAISE EXCEPTION 'Requested K4/K5 E2E fixture already exists or conflicts';
    END IF;
END;
$guard$;

WITH instructor AS (
    INSERT INTO public.users (cognito_sub, name, email, role)
    VALUES (
        'k4-k5-e2e__LESSON_ID__-instructor', 'K4 K5 E2E __LESSON_ID__ Instructor',
        'k4-k5-e2e__LESSON_ID__-instructor@example.invalid', 'INSTRUCTOR'
    )
    RETURNING id
), course AS (
    INSERT INTO public.courses (
        instructor_id, title, description, learning_objectives, status
    )
    SELECT id, 'K4 K5 Full E2E Test __LESSON_ID__',
           'Synthetic isolated AWS E2E fixture',
           '["Verify K4 to K5 automatic orchestration"]'::jsonb, 'DRAFT'
    FROM instructor
    RETURNING id
), section AS (
    INSERT INTO public.sections (course_id, title, position)
    SELECT id, 'Automatic Pipeline', 1 FROM course
    RETURNING id
), lesson AS (
    INSERT INTO public.lessons (section_id, title, position, status, retry_count)
    SELECT id, 'K4 K5 Automatic E2E __LESSON_ID__', 1, 'DRAFT', 0
    FROM section
    RETURNING id
), checked_lesson AS (
    SELECT id FROM lesson WHERE id = __LESSON_ID__
)
INSERT INTO public.video_uploads (
    id, lesson_id, source_key, content_type, size_bytes, expires_at
)
SELECT '__UPLOAD_ID__', id,
       'lessons/__LESSON_ID__/raw/__UPLOAD_ID__.mp4',
       'video/mp4', __VIDEO_SIZE_BYTES__, pg_catalog.now() + interval '24 hours'
FROM checked_lesson;

DO $verify$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM public.lessons l
        JOIN public.video_uploads u ON u.lesson_id = l.id
        WHERE l.id = __LESSON_ID__ AND l.status = 'DRAFT' AND l.retry_count = 0
          AND l.raw_video_key IS NULL AND l.processed_video_key IS NULL
          AND u.id = '__UPLOAD_ID__'
          AND u.source_key = 'lessons/__LESSON_ID__/raw/__UPLOAD_ID__.mp4'
          AND u.content_type = 'video/mp4' AND u.size_bytes = __VIDEO_SIZE_BYTES__
    ) OR EXISTS (
        SELECT 1 FROM public.video_pipeline_runs WHERE upload_id = '__UPLOAD_ID__'
    ) THEN
        RAISE EXCEPTION 'Rendered K4/K5 E2E fixture contract failed';
    END IF;
END;
$verify$;

COMMIT;

SELECT __LESSON_ID__ AS lesson_id,
       '__UPLOAD_ID__' AS upload_id,
       '__RUN_ID__' AS expected_run_id,
       'lessons/__LESSON_ID__/raw/__UPLOAD_ID__.mp4' AS raw_s3_key,
       'lessons/__LESSON_ID__/processed/__UPLOAD_ID__/attempt-1/video_720p.mp4' AS expected_output_key,
       'ai-transcripts/__RUN_ID__/transcript.json' AS expected_transcript_key;
