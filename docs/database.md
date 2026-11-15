# Cơ sở dữ liệu

## Nguồn chuẩn

`database/schema.sql` là snapshot khởi tạo cho database mới. `database/migrations/` chứa các thay đổi tiếp theo cùng những migration lịch sử/nhánh thay thế. Không thể suy ra version database đang chạy chỉ từ các file này; phải kiểm tra registry và object thực tế. Lịch sử migration có các version trùng quanh `0004`; đọc [lịch sử và quy ước migration](../database/migrations/README.md) trước khi chạy SQL.

Database sử dụng PostgreSQL; schema khởi tạo dùng khóa chính `SERIAL` kiểu integer. SQLAlchemy model nằm trong `backend/app/models/`. Schema RDS và migration registry hiện tại chưa được kiểm tra trong lượt cập nhật tài liệu này.

## Các bảng khởi tạo

| Bảng | Mục đích và quan hệ chính |
|---|---|
| `users` | Danh tính người dùng, email/Cognito subject duy nhất, role và trạng thái hoạt động. |
| `courses` | Khóa học do instructor/admin sở hữu. |
| `sections` | Các chương có thứ tự thuộc khóa học. |
| `lessons` | Nội dung bài học có thứ tự và trạng thái xử lý video, thuộc một chương. |
| `enrollments` | Quan hệ student-khóa học; mỗi cặp chỉ có một bản ghi. |
| `lesson_progress` | Tiến độ phát video và trạng thái hoàn tất theo student/bài học. |
| `viewing_sessions` | Theo dõi thứ tự cập nhật trong phiên xem. |
| `progress_updates` | Ledger request/response cho cập nhật tiến độ idempotent. |
| `quizzes` | Tối đa một quiz cho mỗi chương theo schema khởi tạo. |
| `questions` | Câu hỏi, lựa chọn và đáp án đúng lưu phía server. |
| `quiz_attempts` | Lượt nộp quiz, điểm và trạng thái đạt. |
| `quiz_answers` | Câu trả lời từng câu thuộc một lượt làm quiz. |
| `flashcards` | Flashcard có thứ tự, gắn với bài học. |
| `tutor_sessions` | Phiên học bù của student, có thể liên kết tới một lượt làm quiz. |
| `tutor_messages` | Tin nhắn user/assistant trong phiên Tutor. |
| `schema_migrations` | Registry ghi nhận version migration đã áp dụng. |

Migration bổ sung hoặc đối soát các cấu trúc khác, gồm bảng upload/pipeline ledger, trạng thái idempotency/remediation cho checkpoint và các trường tài khoản/tiến độ. Bản nháp review được lưu theo model nội dung lesson/quiz hiện có, không dùng bảng riêng `review_drafts`. Không giả định bảng/cột chỉ có trong migration đã tồn tại ở mọi database nếu chưa kiểm tra registry/schema.

## Quan hệ và ràng buộc

```text
users ──< courses ──< sections ──< lessons ──< flashcards
users >──< courses       qua enrollments
users ──< lesson_progress / viewing_sessions / progress_updates
sections ── 0..1 quizzes ──< questions
users ──< quiz_attempts ──< quiz_answers >── questions
users ──< tutor_sessions ──< tutor_messages
```

Foreign key và trigger xác minh role bảo vệ các quan hệ quan trọng. Unique constraint ngăn enrollment trùng, trùng vị trí lesson/section, trùng số lượt quiz và trùng câu trả lời theo question/attempt. Đáp án quiz được giữ ở server; response quiz trước khi nộp không được làm lộ đáp án. Backend vẫn phải kiểm tra quyền ngoài các ràng buộc SQL.

## Trạng thái migration và kiểm thử

- SQL bootstrap và migration script hiện có trong source.
- Có integration test bao phủ migration PostgreSQL. Báo cáo regression backend gần nhất ghi nhận 69 test có PostgreSQL gate bị skip; các trường hợp đó chưa chứng minh hành vi trên PostgreSQL thật.
- Trạng thái migration trên AWS/RDS **chưa được xác minh**. Không chạy migration runner trên database dùng chung/production nếu chưa review target, backup, preflight, kế hoạch apply và postflight.
- Tài liệu chuyên biệt về review/backup/apply/verify nằm trong [`database/`](database/); quy trình chuẩn ở [migration README](../database/migrations/README.md).

Để xem đầy đủ DDL, constraint và index, đọc [schema khởi tạo](../database/schema.sql) cùng từng migration. Phần tóm tắt này không giả định database đang chạy trùng với snapshot trong repository.
