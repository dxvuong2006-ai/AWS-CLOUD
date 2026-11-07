-- 0004_remove_approved_lesson_status.sql
-- Sau review, lesson được publish trực tiếp; APPROVED không còn trạng thái hợp lệ.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

LOCK TABLE public.lessons IN ACCESS EXCLUSIVE MODE;

UPDATE lessons
SET status = 'PUBLISHED',
    updated_at = NOW()
WHERE status = 'APPROVED';

ALTER TABLE lessons DROP CONSTRAINT IF EXISTS lessons_status_check;
ALTER TABLE lessons DROP CONSTRAINT IF EXISTS ck_lessons_status;
ALTER TABLE lessons ADD CONSTRAINT ck_lessons_status CHECK (
    status IN (
        'DRAFT', 'UPLOADED', 'PROCESSING', 'TRANSCRIBING',
        'AI_PROCESSING', 'REVIEW_REQUIRED', 'PUBLISHED', 'FAILED'
    )
) NOT VALID;
ALTER TABLE lessons VALIDATE CONSTRAINT ck_lessons_status;

INSERT INTO schema_migrations (version, description)
VALUES ('0004', 'Remove approved lesson status; publish directly after review')
ON CONFLICT (version) DO NOTHING;

COMMIT;
