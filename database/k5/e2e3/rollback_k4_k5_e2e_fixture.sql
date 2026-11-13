-- Manual rollback for fixture 3 only. Stop the TEST state machine first.
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
    IF NOT EXISTS (
        SELECT 1 FROM public.users
        WHERE cognito_sub = 'k4-k5-e2e3-instructor'
          AND email = 'k4-k5-e2e3-instructor@example.invalid'
    ) OR NOT EXISTS (
        SELECT 1 FROM public.lessons l
        JOIN public.sections s ON s.id = l.section_id
        JOIN public.courses c ON c.id = s.course_id
        JOIN public.users u ON u.id = c.instructor_id
        WHERE l.id = 3 AND u.cognito_sub = 'k4-k5-e2e3-instructor'
    ) THEN
        RAISE EXCEPTION 'Fixture 3 identity mismatch; refusing rollback';
    END IF;
END;
$guard$;

DELETE FROM public.video_pipeline_runs
WHERE upload_id = '00000000000000000000000000000003';

DELETE FROM public.video_uploads
WHERE id = '00000000000000000000000000000003' AND lesson_id = 3;

DELETE FROM public.courses c
USING public.users u
WHERE c.instructor_id = u.id
  AND u.cognito_sub = 'k4-k5-e2e3-instructor'
  AND u.email = 'k4-k5-e2e3-instructor@example.invalid'
  AND c.title = 'K4 K5 Full E2E Test 3';

DELETE FROM public.users
WHERE cognito_sub = 'k4-k5-e2e3-instructor'
  AND email = 'k4-k5-e2e3-instructor@example.invalid';

DO $verify$
BEGIN
    IF EXISTS (SELECT 1 FROM public.lessons WHERE id = 3)
       OR EXISTS (
           SELECT 1 FROM public.video_uploads
           WHERE id = '00000000000000000000000000000003'
       )
       OR EXISTS (
           SELECT 1 FROM public.users
           WHERE cognito_sub = 'k4-k5-e2e3-instructor'
       ) THEN
        RAISE EXCEPTION 'Fixture 3 rollback verification failed';
    END IF;
END;
$verify$;

COMMIT;
