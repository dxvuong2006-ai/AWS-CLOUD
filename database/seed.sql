-- ============================================================
-- LearnCloud - Demo seed data
-- Phu hop schema.sql hien tai, bao gom cac bang hoc tap/AI.
-- Idempotent: co the chay lai ma khong tao ban ghi trung theo khoa tu nhien.
-- Chay tu project root trong PowerShell:
-- Get-Content .\database\seed.sql | docker exec -i learncloud-db psql -v ON_ERROR_STOP=1 -U learncloud -d learncloud

BEGIN;

-- 1. USERS
INSERT INTO users (cognito_sub, name, email, role)
VALUES
 ('seed-instructor-001', 'Nguyen Minh Anh', 'instructor@example.com', 'INSTRUCTOR'),
 ('seed-instructor-002', 'Tran Quoc Bao', 'instructor2@example.com', 'INSTRUCTOR'),
 ('seed-admin-001', 'LearnCloud Admin', 'admin@example.com', 'ADMIN'),
 ('seed-student-001', 'Le Minh Khang', 'student@example.com', 'STUDENT'),
 ('seed-student-002', 'Pham Thu Ha', 'student2@example.com', 'STUDENT'),
 ('seed-student-003', 'Nguyen Gia Huy', 'student3@example.com', 'STUDENT'),
 ('seed-student-004', 'Tran Bao Ngoc', 'student4@example.com', 'STUDENT'),
 ('seed-student-005', 'Do Duc Minh', 'student5@example.com', 'STUDENT')
ON CONFLICT (email) DO UPDATE SET
 name = EXCLUDED.name,
 role = EXCLUDED.role;

-- 2. COURSES
INSERT INTO courses (instructor_id, title, description, learning_objectives, status)
SELECT u.id, v.title, v.description, v.objectives::jsonb, v.status
FROM (VALUES
 ('instructor@example.com', 'AWS Fundamentals',
  'Nhap mon dien toan dam may va cac dich vu AWS pho bien.',
  '["Giai thich mo hinh cloud", "Phan biet IaaS, PaaS va SaaS", "Mo ta Amazon S3 va IAM"]', 'PUBLISHED'),
 ('instructor@example.com', 'Docker Essentials',
  'Hoc container, image va cac lenh Docker co ban qua vi du thuc hanh.',
  '["Phan biet image va container", "Build image tu Dockerfile", "Chay va quan ly container"]', 'PUBLISHED'),
 ('instructor2@example.com', 'Python for Data Analysis',
  'Khoa hoc mau dang duoc giang vien chuan bi, chua cong bo cho hoc vien.',
  '["Doc va xu ly du lieu bang Python", "Lam quen voi pandas", "Tong hop du lieu"]', 'DRAFT')
) AS v(instructor_email, title, description, objectives, status)
JOIN users u ON u.email = v.instructor_email
WHERE u.role IN ('INSTRUCTOR','ADMIN')
AND NOT EXISTS (
 SELECT 1 FROM courses c WHERE c.instructor_id=u.id AND c.title=v.title
);

-- 3. SECTIONS (position is unique within a course)
INSERT INTO sections (course_id, title, position)
SELECT c.id, v.section_title, v.position
FROM (VALUES
 ('AWS Fundamentals','Cloud Computing Basics',1),
 ('AWS Fundamentals','AWS Storage and Security',2),
 ('Docker Essentials','Containers and Images',1),
 ('Docker Essentials','Docker Workflow',2),
 ('Python for Data Analysis','Python Data Basics',1),
 ('Python for Data Analysis','Working with Tables',2)
) v(course_title, section_title, position)
JOIN courses c ON c.title=v.course_title
WHERE NOT EXISTS (
 SELECT 1 FROM sections s WHERE s.course_id=c.id AND s.position=v.position
);

-- 4. LESSONS
INSERT INTO lessons (
 section_id, title, position, raw_video_key, processed_video_key, status,
 transcript_json, summary, key_concepts_json, duration_seconds
)
SELECT s.id, v.lesson_title, v.position, NULL, NULL, v.status,
 v.transcript::jsonb, v.summary, v.concepts::jsonb, v.duration
FROM (VALUES
 ('AWS Fundamentals','Cloud Computing Basics','What Is Cloud Computing?',1,'PUBLISHED',
  '{"segments":[{"start":0.0,"end":18.0,"text":"Cloud computing cung cap tai nguyen CNTT qua mang theo nhu cau."},{"start":18.0,"end":42.0,"text":"Nguoi dung co the mo rong tai nguyen ma khong can tu mua may chu."}]}',
  'Cloud computing cung cap tai nguyen tinh toan qua internet theo nhu cau, giup mo rong linh hoat va tra phi theo muc su dung.',
  '["Cloud computing","Scalability","Pay-as-you-go"]',240),
 ('AWS Fundamentals','Cloud Computing Basics','Cloud Service Models',2,'PUBLISHED',
  '{"segments":[{"start":0.0,"end":20.0,"text":"IaaS cung cap ha tang, PaaS cung cap nen tang va SaaS cung cap phan mem."}]}',
  'IaaS, PaaS va SaaS khac nhau o muc do quan ly ha tang va ung dung ma nha cung cap dam nhan.',
  '["IaaS","PaaS","SaaS"]',310),
 ('AWS Fundamentals','AWS Storage and Security','Introduction to Amazon S3',1,'PUBLISHED',
  '{"segments":[{"start":0.0,"end":24.0,"text":"Amazon S3 la dich vu object storage."}]}',
  'Amazon S3 luu du lieu duoi dang object trong bucket va phu hop voi tep, media va artifact.',
  '["Amazon S3","Object storage","Bucket"]',285),
 ('AWS Fundamentals','AWS Storage and Security','Identity and Access Management',2,'PUBLISHED',
  '{"segments":[{"start":0.0,"end":25.0,"text":"IAM quan ly danh tinh va quyen truy cap vao tai nguyen AWS."}]}',
  'IAM dung users, roles va policies de kiem soat ai duoc phep thuc hien hanh dong nao.',
  '["IAM","Role","Policy","Least privilege"]',360),
 ('Docker Essentials','Containers and Images','Image vs Container',1,'PUBLISHED',
  '{"segments":[{"start":0.0,"end":22.0,"text":"Image la mau chi doc, container la instance dang chay tu image."}]}',
  'Docker image la ban mau de tao container; container la moi truong thuc thi duoc tao tu image.',
  '["Docker image","Container","Layer"]',270),
 ('Docker Essentials','Containers and Images','Writing a Dockerfile',2,'PUBLISHED',
  '{"segments":[{"start":0.0,"end":20.0,"text":"Dockerfile mo ta cac buoc tao image."}]}',
  'Dockerfile khai bao image co so, thu muc lam viec, cac lenh cai dat va lenh khoi dong.',
  '["Dockerfile","FROM","RUN","CMD"]',390),
 ('Docker Essentials','Docker Workflow','Ports and Volumes',1,'PUBLISHED',
  '{"segments":[{"start":0.0,"end":20.0,"text":"Port mapping cong bo dich vu container ra may host."}]}',
  'Port mapping cho phep truy cap ung dung trong container; volume giu du lieu ben ngoai vong doi container.',
  '["Port mapping","Volume","Persistence"]',330),
 ('Docker Essentials','Docker Workflow','Docker Compose Basics',2,'PUBLISHED',
  '{"segments":[{"start":0.0,"end":20.0,"text":"Compose khai bao nhieu service trong mot file YAML."}]}',
  'Docker Compose giup khai bao va chay nhieu service lien quan trong cung mot ung dung.',
  '["Docker Compose","Service","YAML"]',420),
 ('Python for Data Analysis','Python Data Basics','Lists and Dictionaries',1,'DRAFT',
  '{"segments":[]}',
  'Bai nhap mon ve cau truc du lieu Python; dang cho giang vien kiem duyet.',
  '["List","Dictionary","Iteration"]',300),
 ('Python for Data Analysis','Working with Tables','Introduction to pandas',1,'DRAFT',
  '{"segments":[]}',
  'Gioi thieu DataFrame va thao tac doc bang du lieu; chua publish.',
  '["pandas","DataFrame","CSV"]',360)
) v(course_title,section_title,lesson_title,position,status,transcript,summary,concepts,duration)
JOIN courses c ON c.title=v.course_title
JOIN sections s ON s.course_id=c.id AND s.title=v.section_title
WHERE NOT EXISTS (
 SELECT 1 FROM lessons l WHERE l.section_id=s.id AND l.position=v.position
);

-- 5. FLASHCARDS
INSERT INTO flashcards (lesson_id, front, back, position, is_approved)
SELECT l.id, v.front, v.back, v.position, v.approved
FROM (VALUES
 ('AWS Fundamentals','What Is Cloud Computing?','Cloud computing la gi?','Cach cung cap tai nguyen tinh toan qua mang theo nhu cau.',1,TRUE),
 ('AWS Fundamentals','What Is Cloud Computing?','Scalability','Kha nang tang/giam tai nguyen de dap ung nhu cau su dung.',2,TRUE),
 ('AWS Fundamentals','Cloud Service Models','IaaS, PaaS va SaaS','IaaS cung cap ha tang; PaaS cung cap nen tang; SaaS cung cap ung dung hoan chinh.',1,TRUE),
 ('AWS Fundamentals','Introduction to Amazon S3','Amazon S3 bucket','Don vi chua object trong Amazon S3.',1,TRUE),
 ('AWS Fundamentals','Identity and Access Management','IAM least privilege','Chi cap cac quyen toi thieu can thiet de thuc hien cong viec.',1,TRUE),
 ('Docker Essentials','Image vs Container','Docker image','Mau chi doc dung de tao container.',1,TRUE),
 ('Docker Essentials','Image vs Container','Docker container','Moi truong thuc thi duoc tao tu image.',2,TRUE),
 ('Docker Essentials','Writing a Dockerfile','Dockerfile','Tep khai bao cac buoc de build Docker image.',1,TRUE),
 ('Docker Essentials','Ports and Volumes','Docker volume','Co che luu du lieu ben ngoai vong doi container.',1,TRUE),
 ('Python for Data Analysis','Introduction to pandas','pandas DataFrame','Cau truc du lieu dang bang gom hang va cot.',1,FALSE)
) v(course_title,lesson_title,front,back,position,approved)
JOIN courses c ON c.title=v.course_title
JOIN sections s ON s.course_id=c.id AND s.title=CASE
 WHEN v.lesson_title IN ('What Is Cloud Computing?','Cloud Service Models') THEN 'Cloud Computing Basics'
 WHEN v.lesson_title IN ('Introduction to Amazon S3','Identity and Access Management') THEN 'AWS Storage and Security'
 WHEN v.lesson_title IN ('Image vs Container','Writing a Dockerfile') THEN 'Containers and Images'
 WHEN v.lesson_title IN ('Ports and Volumes') THEN 'Docker Workflow'
 ELSE 'Working with Tables' END
JOIN lessons l ON l.section_id=s.id AND l.title=v.lesson_title
WHERE NOT EXISTS (
 SELECT 1 FROM flashcards f WHERE f.lesson_id=l.id AND f.position=v.position
);

-- 6. ENROLLMENTS: all students enroll in published courses only
INSERT INTO enrollments (student_id, course_id)
SELECT u.id, c.id
FROM users u
CROSS JOIN courses c
WHERE u.role='STUDENT'
  AND c.status='PUBLISHED'
  AND c.title IN ('AWS Fundamentals','Docker Essentials')
ON CONFLICT (student_id, course_id) DO NOTHING;

-- 7. LESSON PROGRESS: mixed progress for dashboard demo
INSERT INTO lesson_progress (student_id, lesson_id, watched_seconds, completed)
SELECT u.id, l.id, v.watched_seconds, v.completed
FROM (VALUES
 ('student@example.com','AWS Fundamentals','What Is Cloud Computing?',240,TRUE),
 ('student@example.com','AWS Fundamentals','Cloud Service Models',310,TRUE),
 ('student@example.com','AWS Fundamentals','Introduction to Amazon S3',285,TRUE),
 ('student2@example.com','AWS Fundamentals','What Is Cloud Computing?',120,TRUE),
 ('student2@example.com','AWS Fundamentals','Cloud Service Models',90,FALSE),
 ('student3@example.com','AWS Fundamentals','What Is Cloud Computing?',70,FALSE),
 ('student4@example.com','AWS Fundamentals','What Is Cloud Computing?',240,TRUE),
 ('student4@example.com','AWS Fundamentals','Cloud Service Models',310,TRUE),
 ('student5@example.com','Docker Essentials','Image vs Container',270,TRUE),
 ('student5@example.com','Docker Essentials','Writing a Dockerfile',100,FALSE)
) v(email,course_title,lesson_title,watched_seconds,completed)
JOIN users u ON u.email=v.email
JOIN courses c ON c.title=v.course_title
JOIN sections s ON s.course_id=c.id
JOIN lessons l ON l.section_id=s.id AND l.title=v.lesson_title
WHERE NOT EXISTS (
 SELECT 1 FROM lesson_progress p WHERE p.student_id=u.id AND p.lesson_id=l.id
);

-- 8. QUIZZES: one checkpoint per section
INSERT INTO quizzes (section_id, title, passing_score, is_approved)
SELECT s.id, v.title, 80.00, v.approved
FROM (VALUES
 ('AWS Fundamentals','Cloud Computing Basics','Checkpoint 1: Cloud Basics',TRUE),
 ('AWS Fundamentals','AWS Storage and Security','Checkpoint 2: AWS Storage and Security',TRUE),
 ('Docker Essentials','Containers and Images','Checkpoint 1: Containers and Images',TRUE),
 ('Docker Essentials','Docker Workflow','Checkpoint 2: Docker Workflow',TRUE),
 ('Python for Data Analysis','Python Data Basics','Checkpoint 1: Python Data Basics',FALSE),
 ('Python for Data Analysis','Working with Tables','Checkpoint 2: Working with Tables',FALSE)
) v(course_title,section_title,title,approved)
JOIN courses c ON c.title=v.course_title
JOIN sections s ON s.course_id=c.id AND s.title=v.section_title
WHERE NOT EXISTS (SELECT 1 FROM quizzes q WHERE q.section_id=s.id);

-- 9. QUESTIONS
INSERT INTO questions (quiz_id, question, options_json, correct_answer, explanation, topic, source_start_seconds, source_end_seconds, position)
SELECT q.id, v.question, v.options::jsonb, v.correct_answer, v.explanation, v.topic,
 v.start_sec, v.end_sec, v.position
FROM (VALUES
 ('Checkpoint 1: Cloud Basics','Cloud computing cung cap tai nguyen theo cach nao?','["Mua va tu van hanh tat ca may chu","Theo nhu cau qua mang","Chi dung tren may tinh ca nhan","Khong can ket noi mang"]','Theo nhu cau qua mang','Tai nguyen cloud co the duoc cap phat qua mang theo nhu cau.','Cloud computing',0.0,18.0,1),
 ('Checkpoint 1: Cloud Basics','Mo hinh nao cung cap ung dung hoan chinh cho nguoi dung?','["IaaS","PaaS","SaaS","Bare metal"]','SaaS','SaaS cung cap phan mem san sang su dung.','Service models',18.0,42.0,2),
 ('Checkpoint 2: AWS Storage and Security','Amazon S3 chu yeu la dich vu gi?','["Object storage","Relational database","Virtual machine","DNS"]','Object storage','S3 luu du lieu duoi dang object trong bucket.','Amazon S3',0.0,24.0,1),
 ('Checkpoint 2: AWS Storage and Security','Nguyen tac least privilege nghia la gi?','["Cap quyen admin cho moi user","Chi cap quyen toi thieu can thiet","Tat ca policy deu public","Dung chung mot tai khoan"]','Chi cap quyen toi thieu can thiet','Least privilege giam quyen truy cap khong can thiet.','IAM',0.0,25.0,2),
 ('Checkpoint 1: Containers and Images','Docker container duoc tao tu thanh phan nao?','["Docker image","Docker volume","Docker network","Docker registry only"]','Docker image','Image la mau de tao container.','Container',0.0,22.0,1),
 ('Checkpoint 1: Containers and Images','Tep nao mo ta cac buoc build image?','["compose.lock","Dockerfile","README.md","requirements-only.txt"]','Dockerfile','Dockerfile mo ta cac lenh build image.','Dockerfile',0.0,20.0,2),
 ('Checkpoint 2: Docker Workflow','Port mapping dung de lam gi?','["Luu du lieu lau dai","Cong bo cong container ra host","Build image tu source","Xoa image cu"]','Cong bo cong container ra host','Port mapping tao ket noi tu cong host toi cong container.','Port mapping',0.0,20.0,1),
 ('Checkpoint 2: Docker Workflow','Co che nao phu hop de giu du lieu khi xoa container?','["Volume","Tag","Layer cache","CMD"]','Volume','Volume tach du lieu khoi vong doi container.','Volume',0.0,20.0,2)
) v(quiz_title,question,options,correct_answer,explanation,topic,start_sec,end_sec,position)
JOIN quizzes q ON q.title=v.quiz_title
WHERE NOT EXISTS (SELECT 1 FROM questions x WHERE x.quiz_id=q.id AND x.position=v.position);

-- 10. QUIZ ATTEMPTS: scores deliberately cover pass, review, and remediation
INSERT INTO quiz_attempts (student_id, quiz_id, score, passed, attempt_number)
SELECT u.id, q.id, v.score, v.score >= q.passing_score, v.attempt_number
FROM (VALUES
 ('student@example.com','Checkpoint 1: Cloud Basics',100.00,1),
 ('student2@example.com','Checkpoint 1: Cloud Basics',50.00,1),
 ('student3@example.com','Checkpoint 1: Cloud Basics',25.00,1),
 ('student3@example.com','Checkpoint 1: Cloud Basics',100.00,2),
 ('student4@example.com','Checkpoint 1: Cloud Basics',100.00,1),
 ('student5@example.com','Checkpoint 1: Containers and Images',50.00,1),
 ('student@example.com','Checkpoint 2: AWS Storage and Security',100.00,1)
) v(email,quiz_title,score,attempt_number)
JOIN users u ON u.email=v.email
JOIN quizzes q ON q.title=v.quiz_title
WHERE NOT EXISTS (
 SELECT 1 FROM quiz_attempts a
 WHERE a.student_id=u.id AND a.quiz_id=q.id AND a.attempt_number=v.attempt_number
);

-- 11. QUIZ ANSWERS: representative answers for the first checkpoint
INSERT INTO quiz_answers (attempt_id, question_id, selected_answer, is_correct)
SELECT a.id, qu.id, v.selected_answer, v.selected_answer=qu.correct_answer
FROM (VALUES
 ('student@example.com','Checkpoint 1: Cloud Basics',1,'Theo nhu cau qua mang'),
 ('student@example.com','Checkpoint 1: Cloud Basics',2,'SaaS'),
 ('student2@example.com','Checkpoint 1: Cloud Basics',1,'Mua va tu van hanh tat ca may chu'),
 ('student2@example.com','Checkpoint 1: Cloud Basics',2,'SaaS'),
 ('student3@example.com','Checkpoint 1: Cloud Basics',1,'Mua va tu van hanh tat ca may chu'),
 ('student3@example.com','Checkpoint 1: Cloud Basics',2,'PaaS')
) v(email,quiz_title,question_position,selected_answer)
JOIN users u ON u.email=v.email
JOIN quizzes q ON q.title=v.quiz_title
JOIN quiz_attempts a ON a.student_id=u.id AND a.quiz_id=q.id
 AND a.attempt_number=1
JOIN questions qu ON qu.quiz_id=q.id AND qu.position=v.question_position
WHERE NOT EXISTS (
 SELECT 1 FROM quiz_answers qa WHERE qa.attempt_id=a.id AND qa.question_id=qu.id
);

-- 12. TUTOR SESSIONS + MESSAGES: sample remediation conversation
INSERT INTO tutor_sessions (student_id, lesson_id, attempt_id)
SELECT u.id, l.id, a.id
FROM users u
JOIN courses c ON c.title='AWS Fundamentals'
JOIN sections s ON s.course_id=c.id AND s.title='Cloud Computing Basics'
JOIN lessons l ON l.section_id=s.id AND l.title='Cloud Service Models'
JOIN quizzes q ON q.section_id=s.id AND q.title='Checkpoint 1: Cloud Basics'
JOIN quiz_attempts a ON a.student_id=u.id AND a.quiz_id=q.id AND a.attempt_number=1
WHERE u.email='student2@example.com'
AND NOT EXISTS (
 SELECT 1 FROM tutor_sessions ts WHERE ts.student_id=u.id AND ts.lesson_id=l.id AND ts.attempt_id=a.id
);

INSERT INTO tutor_messages (session_id, role, content)
SELECT ts.id, v.role, v.content
FROM tutor_sessions ts
JOIN users u ON u.id=ts.student_id AND u.email='student2@example.com'
JOIN lessons l ON l.id=ts.lesson_id AND l.title='Cloud Service Models'
CROSS JOIN (VALUES
 ('USER','Em hay nham lan giua IaaS, PaaS va SaaS.'),
 ('ASSISTANT','Hay nho theo muc do quan ly: IaaS cung cap ha tang; PaaS cung cap nen tang de phat trien; SaaS la ung dung hoan chinh.'),
 ('ASSISTANT','Vi du: may ao la IaaS, nen tang deploy ung dung co the la PaaS, con email tren web la SaaS.'),
 ('ASSISTANT','Luyen tap: dich vu cung cap phan mem hoan chinh qua trinh duyet thuoc mo hinh nao?')
) v(role,content)
WHERE NOT EXISTS (
 SELECT 1 FROM tutor_messages tm WHERE tm.session_id=ts.id AND tm.role=v.role AND tm.content=v.content
);

COMMIT;

-- Quick validation queries (run separately if needed):
-- SELECT role, COUNT(*) FROM users GROUP BY role ORDER BY role;
-- SELECT title, status FROM courses ORDER BY title;
-- SELECT q.title, COUNT(DISTINCT qu.id) AS questions
-- FROM quizzes q LEFT JOIN questions qu ON qu.quiz_id=q.id GROUP BY q.id,q.title ORDER BY q.title;
-- SELECT u.email, q.title, a.score, a.passed, a.attempt_number
-- FROM quiz_attempts a JOIN users u ON u.id=a.student_id JOIN quizzes q ON q.id=a.quiz_id
-- ORDER BY u.email,q.title,a.attempt_number;
