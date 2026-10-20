-- ============================================================
-- LearnCloud - Sample Data
-- Seeds all 5 tables:
-- users, courses, sections, lessons, enrollments
--
-- Run from project root in PowerShell:
-- Get-Content .\database\seed.sql | docker exec -i learncloud-db psql -v ON_ERROR_STOP=1 -U learncloud -d learncloud
-- ============================================================

BEGIN;

-- ============================================================
-- 1. USERS
-- ============================================================

INSERT INTO users (cognito_sub, name, email, role)
VALUES
    ('seed-instructor-001', 'Demo Instructor', 'instructor@example.com', 'INSTRUCTOR'),
    ('seed-student-001', 'Demo Student', 'student@example.com', 'STUDENT'),
    ('seed-student-002', 'Demo Student 2', 'student2@example.com', 'STUDENT')
ON CONFLICT (email) DO NOTHING;


-- ============================================================
-- 2. COURSES
-- ============================================================

INSERT INTO courses (
    instructor_id,
    title,
    description,
    learning_objectives,
    status
)
SELECT
    instructor.id,
    sample.title,
    sample.description,
    sample.learning_objectives::jsonb,
    sample.status
FROM users AS instructor
CROSS JOIN (
    VALUES
        (
            'Introduction to AWS',
            'Learn the basics of AWS Cloud.',
            '["Understand cloud computing", "Learn core AWS services", "Understand basic cloud architecture"]',
            'PUBLISHED'
        ),
        (
            'Introduction to Docker',
            'Learn containerization and Docker fundamentals.',
            '["Understand containers", "Build Docker images", "Run containers"]',
            'DRAFT'
        )
) AS sample(title, description, learning_objectives, status)
WHERE instructor.email = 'instructor@example.com'
  AND instructor.role = 'INSTRUCTOR'
  AND NOT EXISTS (
      SELECT 1
      FROM courses AS existing
      WHERE existing.instructor_id = instructor.id
        AND existing.title = sample.title
  );


-- ============================================================
-- 3. SECTIONS
-- ============================================================

INSERT INTO sections (course_id, title, position)
SELECT
    c.id,
    sample.title,
    sample.position
FROM (
    VALUES
        ('Introduction to AWS', 'Introduction to Cloud Computing', 1),
        ('Introduction to AWS', 'AWS Core Services', 2),
        ('Introduction to Docker', 'Docker Fundamentals', 1),
        ('Introduction to Docker', 'Docker Images and Containers', 2)
) AS sample(course_title, title, position)
JOIN courses AS c
    ON c.title = sample.course_title
JOIN users AS instructor
    ON instructor.id = c.instructor_id
WHERE instructor.email = 'instructor@example.com'
  AND NOT EXISTS (
      SELECT 1
      FROM sections AS existing
      WHERE existing.course_id = c.id
        AND existing.position = sample.position
  );


-- ============================================================
-- 4. LESSONS
-- ============================================================

INSERT INTO lessons (
    section_id,
    title,
    position,
    raw_video_key,
    processed_video_key,
    status,
    transcript_json,
    summary,
    key_concepts_json
)
SELECT
    s.id,
    sample.title,
    sample.position,
    NULL,
    NULL,
    sample.status,
    sample.transcript_json::jsonb,
    sample.summary,
    sample.key_concepts_json::jsonb
FROM (
    VALUES
        (
            'Introduction to AWS',
            'Introduction to Cloud Computing',
            'What Is Cloud Computing?',
            1,
            'PUBLISHED',
            '{"segments":[]}',
            'An introduction to cloud computing concepts and benefits.',
            '["Cloud computing", "Scalability", "Pay-as-you-go"]'
        ),
        (
            'Introduction to AWS',
            'Introduction to Cloud Computing',
            'Cloud Service Models',
            2,
            'PUBLISHED',
            '{"segments":[]}',
            'An overview of IaaS, PaaS and SaaS.',
            '["IaaS", "PaaS", "SaaS"]'
        ),
        (
            'Introduction to AWS',
            'AWS Core Services',
            'Introduction to Amazon S3',
            1,
            'PUBLISHED',
            '{"segments":[]}',
            'Learn the basics of object storage with Amazon S3.',
            '["Amazon S3", "Object storage", "Buckets"]'
        ),
        (
            'Introduction to Docker',
            'Docker Fundamentals',
            'What Is Docker?',
            1,
            'DRAFT',
            '{"segments":[]}',
            'An introduction to Docker and containerization.',
            '["Docker", "Containers", "Images"]'
        ),
        (
            'Introduction to Docker',
            'Docker Images and Containers',
            'Working with Docker Images',
            1,
            'DRAFT',
            '{"segments":[]}',
            'Learn how Docker images are used to create containers.',
            '["Docker images", "Docker containers"]'
        )
) AS sample(
    course_title,
    section_title,
    title,
    position,
    status,
    transcript_json,
    summary,
    key_concepts_json
)
JOIN courses AS c
    ON c.title = sample.course_title
JOIN users AS instructor
    ON instructor.id = c.instructor_id
JOIN sections AS s
    ON s.course_id = c.id
   AND s.title = sample.section_title
WHERE instructor.email = 'instructor@example.com'
  AND NOT EXISTS (
      SELECT 1
      FROM lessons AS existing
      WHERE existing.section_id = s.id
        AND existing.position = sample.position
  );


-- ============================================================
-- 5. ENROLLMENTS
-- Both demo students enroll in the published AWS course.
-- ============================================================

INSERT INTO enrollments (student_id, course_id)
SELECT
    student.id,
    c.id
FROM users AS student
JOIN courses AS c
    ON c.title = 'Introduction to AWS'
JOIN users AS instructor
    ON instructor.id = c.instructor_id
WHERE student.email IN (
    'student@example.com',
    'student2@example.com'
)
  AND student.role = 'STUDENT'
  AND instructor.email = 'instructor@example.com'
  AND c.status = 'PUBLISHED'
ON CONFLICT (student_id, course_id) DO NOTHING;


COMMIT;
