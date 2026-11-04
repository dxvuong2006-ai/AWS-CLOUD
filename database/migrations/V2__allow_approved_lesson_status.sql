-- Chạy trước khi triển khai API review trên PostgreSQL.
-- Hỗ trợ tên constraint của cả schema.sql và SQLAlchemy create_all.
BEGIN;
ALTER TABLE lessons DROP CONSTRAINT IF EXISTS lessons_status_check;
ALTER TABLE lessons DROP CONSTRAINT IF EXISTS ck_lessons_status;
ALTER TABLE lessons ADD CONSTRAINT ck_lessons_status CHECK (
    status IN (
        'DRAFT', 'UPLOADED', 'PROCESSING', 'TRANSCRIBING',
        'AI_PROCESSING', 'REVIEW_REQUIRED', 'APPROVED', 'PUBLISHED', 'FAILED'
    )
);
COMMIT;
