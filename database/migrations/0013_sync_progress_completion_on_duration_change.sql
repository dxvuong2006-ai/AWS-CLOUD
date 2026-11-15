-- Keep persisted LessonProgress completion aligned with the 10% rule when
-- lesson duration is backfilled or corrected after learners have watched.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

DO $preflight$
BEGIN
    IF to_regclass('lessons') IS NULL
       OR to_regclass('lesson_progress') IS NULL
       OR to_regclass('schema_migrations') IS NULL THEN
        RAISE EXCEPTION 'Lessons, lesson_progress, or schema_migrations is missing';
    END IF;

    IF EXISTS (
        SELECT 1 FROM schema_migrations
        WHERE version = '0013'
          AND description <> 'Synchronize lesson progress completion when duration changes'
    ) THEN
        RAISE EXCEPTION 'Migration version 0013 is already used by another change';
    END IF;
END;
$preflight$;

LOCK TABLE lessons IN SHARE ROW EXCLUSIVE MODE;
LOCK TABLE lesson_progress IN SHARE ROW EXCLUSIVE MODE;

-- Reconcile existing rows once, including progress saved before duration backfill.
UPDATE lesson_progress AS progress
SET completed = COALESCE(
    lesson.duration_seconds IS NOT NULL
    AND lesson.duration_seconds > 0
    AND progress.watched_seconds::numeric >= lesson.duration_seconds::numeric * 0.1,
    FALSE
)
FROM lessons AS lesson
WHERE lesson.id = progress.lesson_id
  AND progress.completed IS DISTINCT FROM COALESCE(
      lesson.duration_seconds IS NOT NULL
      AND lesson.duration_seconds > 0
      AND progress.watched_seconds::numeric >= lesson.duration_seconds::numeric * 0.1,
      FALSE
  );

CREATE OR REPLACE FUNCTION sync_lesson_progress_completion_on_duration_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $function$
BEGIN
    IF NEW.duration_seconds IS DISTINCT FROM OLD.duration_seconds THEN
        UPDATE lesson_progress AS progress
        SET completed = COALESCE(
            NEW.duration_seconds IS NOT NULL
            AND NEW.duration_seconds > 0
            AND progress.watched_seconds::numeric >= NEW.duration_seconds::numeric * 0.1,
            FALSE
        )
        WHERE progress.lesson_id = NEW.id
          AND progress.completed IS DISTINCT FROM COALESCE(
              NEW.duration_seconds IS NOT NULL
              AND NEW.duration_seconds > 0
              AND progress.watched_seconds::numeric >= NEW.duration_seconds::numeric * 0.1,
              FALSE
          );
    END IF;
    RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_sync_lesson_progress_completion_on_duration_change
    ON lessons;
CREATE TRIGGER trg_sync_lesson_progress_completion_on_duration_change
AFTER UPDATE OF duration_seconds ON lessons
FOR EACH ROW
EXECUTE FUNCTION sync_lesson_progress_completion_on_duration_change();

INSERT INTO schema_migrations(version, description)
VALUES ('0013', 'Synchronize lesson progress completion when duration changes')
ON CONFLICT (version) DO NOTHING;

COMMIT;
