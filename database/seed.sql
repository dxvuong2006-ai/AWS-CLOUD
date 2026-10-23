INSERT INTO users (
    cognito_sub,
    name,
    email,
    role
)
VALUES (
    'seed-instructor-001',
    'Demo Instructor',
    'instructor@example.com',
    'INSTRUCTOR'
);

INSERT INTO courses (
    instructor_id,
    title,
    description,
    learning_objectives,
    status
)
VALUES
(
    1,
    'Introduction to AWS',
    'Learn the basics of AWS Cloud',
    '["Understand cloud computing", "Learn AWS services"]'::jsonb,
    'PUBLISHED'
),
(
    1,
    'Introduction to Docker',
    'Learn containerization',
    '["Understand containers"]'::jsonb,
    'DRAFT'
);
