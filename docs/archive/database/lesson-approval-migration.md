# [Lịch sử] Review migration phê duyệt Lesson

> **TÀI LIỆU LỊCH SỬ - KHÔNG XÁC MINH HIỆN TẠI.** Thời điểm áp dụng: snapshot review quanh ngày 30/10/2026, trước khi source loại trạng thái `APPROVED`. Không dùng hướng dẫn này để chọn migration hiện tại; xem [thiết kế database](../../02-architecture/database-design.md) và registry/schema của database đích.

> Ghi chú review lịch sử. Trạng thái migration/DB trong tài liệu này không được kiểm tra lại; xác minh schema và registry của đúng database trước khi vận hành. Không xem câu “chưa áp dụng” là trạng thái hiện tại.

## Phạm vi và kết quả đối chiếu

Người dùng đã đổi quyết định: bổ sung APPROVED để có luồng approve hợp lệ rồi
publish Course. Giữ toàn bộ processing-status/retry, quyền sở hữu và điều kiện
publish của giai đoạn 1. Không đổi API Contract Draft, không viết Transcribe/AI,
không tạo tài nguyên AWS, không tự thực thi migration.

Kiểm tra DB `learncloud` thực tế bằng transaction READ ONLY cho thấy:

- `public.lessons.status` là VARCHAR, CHECK `lessons_status_check` có 8 trạng
  thái, thiếu APPROVED. Có 2 Lesson DRAFT và 8 PUBLISHED tại lúc kiểm tra.
- `schema_migrations` có 0001/0002, chưa có 0004; không có approved_by/approved_at.
- Model cũ còn thiếu AI_PROCESSING; bootstrap có AI_PROCESSING nhưng thiếu APPROVED.
- API Contract Draft v4 đã liệt kê đủ 9 trạng thái và endpoint approve. Contract
  chưa chốt approve có tự publish hay không; theo yêu cầu hiện tại, implementation
  **approve chỉ đặt APPROVED, không tự publish**. Course publish là bước riêng.
- Router/service review còn trống trước thay đổi, nên chỉ bổ sung phần approve
  tối thiểu; không tự xây GET/PATCH AI review hoặc tạo nội dung thay thành viên C.

## Trạng thái và kiểm tra hợp lệ

`backend/app/lesson_states.py` là nguồn enum dùng chung cho model, response
validation và các transition mới:

```text
DRAFT → UPLOADED → PROCESSING → TRANSCRIBING → AI_PROCESSING
      → REVIEW_REQUIRED → APPROVED → PUBLISHED
FAILED → PROCESSING  (retry hợp lệ, giữ nguyên cơ chế giai đoạn 1)
```

Model, bootstrap và migration có cùng 9 giá trị; migration không tự chuyển
bất kỳ Lesson nào sang APPROVED. Hai điều kiện vẫn được phân biệt:

- **Schema cho phép APPROVED** không có nghĩa nội dung đã được phê duyệt.
- Chỉ hành động approve của instructor sở hữu course, sau kiểm tra, mới ghi APPROVED.

## Endpoint phê duyệt

`POST /lessons/{lesson_id}/approve`, không có request body; dùng
`require_instructor`/identity hiện tại. Không nhận key, AI content hay status
từ frontend để lách review.

Điều kiện cho một approval mới:

1. Lesson/course tồn tại, Instructor sở hữu course; kiểm tra lại ownership sau khóa.
2. Course ở DRAFT và Lesson ở REVIEW_REQUIRED. Không approve UPLOADED/PROCESSING/
   FAILED hoặc coi PUBLISHED từ seed là bằng chứng approve.
3. Có processed key không rỗng, transcript JSON object/array không rỗng,
   summary không trắng và key_concepts_json là array không rỗng.
4. CHECK chuẩn `ck_lessons_status` đã validated và hỗ trợ APPROVED; nếu chưa có,
   trả 503 `APPROVAL_SCHEMA_NOT_READY`, không chạy DDL hoặc thử ghi APPROVED.
5. HEAD processed object thành công và object không rỗng. Thiếu object trả 409;
   AWS/credentials/quyền truy cập lỗi trả 502, không lộ exception/key/URL cho FE.

Các kiểm tra JSON ở đây là **presence/shape cơ bản**, không tự đánh giá chất
lượng AI hay định dạng transcript chưa được C chốt. Instructor chịu trách nhiệm
review nội dung; C vẫn sở hữu chuẩn hóa/validation chi tiết và review quiz/
flashcard. Endpoint không tự approve quiz/flashcard hoặc tạo transcript/summary.

Response thành công, ví dụ minh họa schema:

```json
{
  "lesson_id": 3,
  "status": "APPROVED",
  "updated_at": "2026-10-30T04:00:00Z"
}
```

Gọi lại khi đã APPROVED và vẫn có quyền trả 200 cùng trạng thái, không HEAD lại
hoặc cập nhật timestamp. Sau Course publish, Lesson là PUBLISHED; gọi approve
lại không được dùng để suy diễn approval cho dữ liệu legacy.

Approve dùng khóa Course → Lesson và NOWAIT giống retry/publish; tranh khóa
trả 409 `REVIEW_BUSY`. Lỗi sau flush/commit được rollback; không tạo job mới,
không đổi retry_count hoặc sửa nội dung AI. Lỗi pipeline cũ được xóa khi approve.

## Xuất bản khóa học

Giữ nguyên ownership/role, khóa transaction và idempotency hiện có. Course
DRAFT chỉ publish khi có section, mọi section có Lesson, mọi Lesson là
APPROVED và có processed key không trắng. Cùng transaction chuyển Lesson và
Course sang PUBLISHED. Course đã PUBLISHED nhận lại lệnh trả 200 không sửa nội dung.
Publish còn kiểm tra lại độ đầy đủ của transcript/summary/concepts, để không
xuất bản khi nội dung đã bị làm rỗng sau approval.

Đặc biệt: không đổi điều kiện thành APPROVED **hoặc** UPLOADED/REVIEW_REQUIRED/
legacy PUBLISHED; không dùng việc upload thành công để thay approval.

## Migration 0004 làm gì

File: `database/migrations/0004_add_lesson_approved_status.sql`.

- BEGIN/COMMIT, lock_timeout 5s và statement_timeout 60s.
- Khóa ACCESS EXCLUSIVE trong transaction để thay CHECK nguyên tử. Có thể chặn
  đọc/ghi, nên operator chọn maintenance window phù hợp; không gọi là zero downtime.
- Chỉ nhận các tên CHECK trạng thái đã biết: lessons_status_check, ck_lessons_status,
  chk_lessons_status. Nếu có CHECK khác đụng status hoặc dữ liệu ngoài tập 9 giá trị,
  script dừng để review, không tự xóa constraint tùy ý hay sửa dữ liệu.
- Thay CHECK bằng `ck_lessons_status`, NOT VALID rồi VALIDATE trước commit;
  giữ nguyên các constraint khác, cột, khóa ngoại và mọi dữ liệu Lesson.
- Ghi version 0004 bằng ON CONFLICT; chặn nếu version này đã được dùng cho thay đổi
  khác. Có thể chạy lại cùng script, nhưng vẫn cần khóa bảng.
- Không DROP TABLE, TRUNCATE, DELETE, backfill hay tự approve; không có migration hook
  trong startup FastAPI/test suite.

Tham khảo cơ chế CHECK/VALIDATE và khóa:
[PostgreSQL ALTER TABLE](https://www.postgresql.org/docs/current/sql-altertable.html).

README cũ từng nhắc 0003_reconcile_legacy_schema.sql nhưng file không tồn tại.
Migration 0004 độc lập với file thiếu đó, dựa trên bootstrap hiện có. Không chạy
script giả để đánh dấu 0003; kiểm tra registry DB chung để tránh trùng version.

## Operator kiểm tra trước — chỉ đọc

Chạy từ repository root. Các lệnh bên dưới là hướng dẫn, Codex **không tự chạy
migration**. Ví dụ container/user/database theo cấu hình local hiện có:

```powershell
Get-Content .\database\migrations\0004_add_lesson_approved_status.sql -Raw

Get-Content .\database\checks\lesson_approval_preflight.sql -Raw |
  docker exec -i learncloud-db psql -v ON_ERROR_STOP=1 -U learncloud -d learncloud
```

Preflight bọc READ ONLY, in DB/schema/version, CHECK definitions, số Lesson theo
status và registry. Trước khi áp dụng, xác minh:

- Đúng DB/schema public; status là VARCHAR như baseline đã kiểm tra.
- Không có CHECK trạng thái tùy biến ngoài danh sách migration hỗ trợ.
- unsupported_statuses = 0; version 0004 chưa bị thay đổi khác sử dụng.
- Ghi lại tổng số Lesson và số dòng từng status để so sánh; có backup/snapshot phù hợp.
- Review script với C/schema owner và thử trên bản sao/test DB do operator chuẩn bị.

Không chạy lại schema.sql để nâng cấp DB hiện hữu. CREATE TABLE IF NOT EXISTS
không cập nhật CHECK của bảng cũ; schema.sql chỉ là bootstrap cho DB mới.

## Áp dụng thủ công sau review

Chỉ operator thực hiện bước này sau khi đã review và backup:

```powershell
Get-Content .\database\migrations\0004_add_lesson_approved_status.sql -Raw |
  docker exec -i learncloud-db psql -v ON_ERROR_STOP=1 -U learncloud -d learncloud
if ($LASTEXITCODE -ne 0) { throw 'Migration failed; inspect the error before retrying.' }
```

Script tự quản lý BEGIN/COMMIT; không coi việc bọc thêm BEGIN/ROLLBACK bên ngoài
là dry run, vì COMMIT trong file có thể kết thúc transaction bao ngoài.
Nếu timeout/validation lỗi, transaction rollback; không tự sửa hoặc xóa dữ liệu
để ép script pass. Không rollback về CHECK 8 trạng thái khi đã có APPROVED;
cần kế hoạch roll-forward/downgrade được review, không đổi trạng thái âm thầm.

Sau đó chạy lại preflight: CHECK phải là ck_lessons_status đã validated, có
APPROVED; registry có 0004; tổng số và phân bố trạng thái Lesson phải giữ nguyên.
Restart backend để nhận code mới, kiểm tra OpenAPI có endpoint approve.

Để kiểm tra nghiệp vụ, chọn **course DRAFT và Lesson REVIEW_REQUIRED có kết quả
xử lý/review thật**, dùng Instructor sở hữu course trong Swagger:

1. Publish trước approve → 409 LESSON_APPROVAL_REQUIRED.
2. POST /lessons/{id}/approve → 200 APPROVED; processing-status đọc APPROVED từ DB.
3. Approve hết Lesson hợp lệ trong course, rồi POST /courses/{id}/publish → 200 PUBLISHED.
4. Retry ở APPROVED/PUBLISHED vẫn bị từ chối vì chỉ retry FAILED.

Không đổi Lesson 8/seed sang REVIEW_REQUIRED chỉ để trình diễn thành công;
không tạo AI content giả hoặc dùng raw video thay processed để vượt gate.

## approved_by / approved_at: đề xuất riêng, chưa thêm

Contract Draft v4 yêu cầu quyền và trạng thái approval, **không bắt buộc** hai
cột này. APPROVED trong status đáp ứng gate hiện tại. Không thêm chúng vào
migration bắt buộc hoặc request/response lần này để tránh mở rộng schema ngoài mục tiêu.

Đề xuất migration riêng khi nhóm chốt nhu cầu audit:

- approved_by INTEGER nullable, FK users(id) với policy xóa được nhóm thống nhất;
- approved_at TIMESTAMPTZ nullable; chỉ ghi từ identity/time của server khi approve;
- không nhận từ frontend, không backfill người/thời điểm giả cho PUBLISHED legacy;
- nếu nội dung thay đổi, cần policy hủy approval/review lại và có thể lưu revision
  được duyệt; trạng thái đơn lẻ không phải audit trail đầy đủ.

Hiện log approval có lesson_id/instructor_id và request timestamp, nhưng không
được coi là thay thế một audit trail bền vững trong DB.

## Kiểm thử và giới hạn xác minh

Chạy từ backend:

```powershell
../.venv/Scripts/python.exe -m unittest discover -s tests/unit -p 'test_*.py' -v
$env:LEARNCLOUD_RUN_DB_TESTS = '1'
../.venv/Scripts/python.exe -m unittest discover -s tests/integration -p 'test_video_processing_db.py' -v
```

- 91 unit/regression tests pass, gồm status-set consistency giữa enum/model/
  bootstrap/migration, approve → publish, quyền/idempotency/concurrency, S3 GET/PUT,
  retry và kiểm tra an toàn tĩnh của script migration/preflight.
- PostgreSQL: 10 tests pass, 1 skip. Test trước migration xác nhận approve trả
  503 an toàn và DB chưa được đổi CHECK; processing-status/retry vẫn hoạt động.
- Test ghi APPROVED rồi publish trong PostgreSQL chỉ chạy khi operator đã áp dụng
  migration trước. Suite **không chạy DDL** để tự mở khóa test; fixture DML dùng
  outer transaction/savepoint và rollback như giai đoạn 1.
- Migration chưa được chạy/đánh giá runtime trên PostgreSQL, kể cả test DB; chỉ
  được review và kiểm tra tĩnh theo đúng yêu cầu không tự áp dụng. Operator cần
  chạy trên bản sao/test DB trước môi trường dùng chung.
- S3 HEAD trong tests được stub; chưa tuyên bố đã approve nội dung/video AWS thật.

## File liên quan đã thay đổi trong lượt điều chỉnh

| Nhóm | File |
| --- | --- |
| Migration/preflight | database/migrations/0004_add_lesson_approved_status.sql; database/checks/lesson_approval_preflight.sql |
| Bootstrap/model/enum | database/schema.sql; backend/app/models/lesson.py; backend/app/lesson_states.py |
| Validation | backend/app/schemas/lesson.py |
| Approve | backend/app/api/review.py; backend/app/services/review_service.py; backend/app/main.py |
| Repository | backend/app/repositories/lessons_repo.py; courses_repo.py |
| Service đồng bộ | backend/app/services/course_service.py; processing_service.py |
| Tests | backend/tests/unit/test_lesson_approval.py; test_video_processing.py; backend/tests/integration/test_video_processing_db.py |
| Tài liệu | database/migrations/README.md; tài liệu tổng hợp hiện nay ở docs/02-architecture/database-design.md; snapshot video hiện ở docs/archive/operations/video-processing-phase1.md; tài liệu này |
