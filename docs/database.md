# Database LearnCloud

## 1. Phạm vi và nguồn chuẩn

LearnCloud sử dụng PostgreSQL. Bản schema khởi tạo hiện tại nằm ở
[`database/schema.sql`](../database/schema.sql), dữ liệu demo ở
[`database/seed.sql`](../database/seed.sql), và thay đổi sau baseline phải theo
[quy ước migration](../database/migrations/README.md).

Schema dùng khóa chính `SERIAL` (`INTEGER`) và thời gian `TIMESTAMPTZ` theo UTC.
Điều này là trạng thái hiện tại của code, dù một số tài liệu kiến trúc cũ từng
đề cập UUID.

## 2. Quan hệ chính

```text
users (instructor) 1 ── * courses 1 ── * sections 1 ── * lessons
users (student)    * ── * courses qua enrollments
users (student)    1 ── * lessons qua lesson_progress
sections            1 ── 1 quizzes 1 ── * questions
users (student)     1 ── * quiz_attempts 1 ── * quiz_answers
lessons              1 ── * flashcards
users (student)      1 ── * tutor_sessions 1 ── * tutor_messages
```

`quiz_attempts` đồng thời tham chiếu tới `quizzes`; `tutor_sessions` có thể
tham chiếu tới một `quiz_attempt` để tạo remediation từ bài làm chưa đạt.

## 3. Bảng và trách nhiệm

| Bảng                | Mục đích                                                        | Ràng buộc đáng chú ý                                                                              |
| ------------------- | --------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `users`             | Danh tính người dùng demo/Cognito và vai trò.                   | `email`, `cognito_sub` là duy nhất; role là `STUDENT`, `INSTRUCTOR` hoặc `ADMIN`.                 |
| `courses`           | Metadata và trạng thái course.                                  | `instructor_id` phải là instructor/admin; status `DRAFT` hoặc `PUBLISHED`.                        |
| `sections`          | Phân đoạn có thứ tự của course.                                 | Duy nhất `(course_id, position)`.                                                                 |
| `lessons`           | Nội dung bài học, video, transcript, summary và pipeline state. | Duy nhất `(section_id, position)`; status bị giới hạn; `duration_seconds`/`retry_count` không âm. |
| `flashcards`        | Flashcard sinh từ hoặc gắn với lesson.                          | Duy nhất `(lesson_id, position)`; front/back không rỗng.                                          |
| `enrollments`       | Liên kết student-course.                                        | Duy nhất `(student_id, course_id)`; student phải có role `STUDENT`.                               |
| `lesson_progress`   | Tiến độ theo student-lesson.                                    | Duy nhất `(student_id, lesson_id)`; watched time không âm.                                        |
| `quizzes`           | Checkpoint của một section.                                     | Một quiz/section; `passing_score` từ 0 đến 100.                                                   |
| `questions`         | Câu hỏi, lựa chọn và đáp án server-side.                        | Duy nhất `(quiz_id, position)`; đáp án phải là key trong `options_json`.                          |
| `quiz_attempts`     | Kết quả một lần làm quiz.                                       | Duy nhất `(student_id, quiz_id, attempt_number)`; score 0–100.                                    |
| `quiz_answers`      | Câu trả lời theo từng câu hỏi trong attempt.                    | Duy nhất `(attempt_id, question_id)`.                                                             |
| `tutor_sessions`    | Phiên remediation của student.                                  | Trigger xác minh student/section khớp quiz attempt nếu có.                                        |
| `tutor_messages`    | Hội thoại thuộc một Tutor session.                              | role chỉ `USER` hoặc `ASSISTANT`; content không rỗng.                                             |
| `schema_migrations` | Các version schema đã được áp dụng.                             | `version` là khóa chính.                                                                          |

## 4. Quy tắc nghiệp vụ được database bảo vệ

- Course chỉ có thể tham chiếu tới user role `INSTRUCTOR` hoặc `ADMIN`.
- Enrollment, progress, quiz attempt và Tutor session chỉ có thể tham chiếu
  tới user role `STUDENT`.
- Dữ liệu con của course/section/lesson bị xóa theo quan hệ `CASCADE` nơi phù
  hợp; không xóa instructor khi còn course (`RESTRICT`).
- `questions.correct_answer` là dữ liệu chấm điểm ở server. API student không
  được trả trường này trước khi nộp bài.
- Một Tutor session có attempt phải thuộc cùng student và cùng section với
  lesson của session; trigger `trg_validate_tutor_session_consistency` kiểm tra
  điều đó.

Các constraint ở database là lớp bảo vệ cuối. Backend vẫn phải kiểm tra quyền
owner, enrollment, publish/review và unlock trước khi đọc/ghi dữ liệu.

## 5. Trạng thái lesson và nội dung AI

`lessons.status` chấp nhận:

```text
DRAFT → UPLOADED → PROCESSING → TRANSCRIBING → AI_PROCESSING
      → REVIEW_REQUIRED → PUBLISHED
```

`FAILED` có thể phát sinh tại các bước xử lý; `error_message` và `retry_count`
giúp theo dõi lỗi/retry. Database chấp nhận các trạng thái trên, nhưng việc ép
đúng chuyển trạng thái và quyền retry vẫn phải do service/API thực hiện.

`transcript_json`, `key_concepts_json`, `learning_objectives` và
`options_json` dùng JSONB để lưu cấu trúc linh hoạt. Code gọi API cần validate
payload bằng schema; không nên coi JSONB là thay thế cho API contract.

## 6. Dữ liệu demo

`seed.sql` tạo idempotent:

- `Demo Instructor` — `instructor@example.com`;
- `Demo Student` — `student@example.com`;
- `Demo Student 2` — `student2@example.com`;
- course published `Introduction to AWS` cùng sections/lessons mẫu;
- course draft `Introduction to Docker`;
- enrollment hai student vào course AWS.

Seed chỉ dành cho local development. Không thêm password thật, access key hoặc
dữ liệu cá nhân vào file này.

## 8. Kiểm tra nhanh

```sql
-- Danh sách bảng
\dt

-- Kiểm tra phiên bản schema
SELECT version, description, applied_at
FROM schema_migrations
ORDER BY version;

-- Xem course cùng số section
SELECT c.id, c.title, c.status, COUNT(s.id) AS section_count
FROM courses c
LEFT JOIN sections s ON s.course_id = c.id
GROUP BY c.id, c.title, c.status
ORDER BY c.id;
```

Có thể chạy truy vấn qua Docker, ví dụ:

```powershell
docker exec -it learncloud-db psql -U learncloud -d learncloud
```

## 9. Khi thay đổi database

1. Xác định contract/API/model nào bị ảnh hưởng.
2. Tạo migration version mới; không sửa migration đã được merge.
3. Cập nhật SQLAlchemy model, schema Pydantic và tài liệu này trong cùng PR.
4. Thử migration trên database sạch và database có seed.
5. Review constraint, index, `ON DELETE`, khả năng rollback và nguy cơ mất dữ
   liệu trước khi merge.
