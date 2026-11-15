# Video Processing Backend

> Ghi nhận lịch sử: một thay đổi Lesson approval đã được chuẩn bị;
> trạng thái migration/DB hiện tại chưa xác minh. Xem [hướng dẫn review](../database/lesson-approval-migration.md).
> Các nhận xét bên dưới về việc giữ nguyên schema/chặn publish là snapshot
> của giai đoạn triển khai ban đầu, không phải quyết định hiện tại.
> Đây là ghi chú lịch sử; kiểm tra route, trạng thái migration và AWS riêng trước khi dựa vào bất kỳ kết luận nào.

## Kết quả và giới hạn đã thống nhất

Đã thêm ba endpoint trong router hiện có; giữ kiến trúc API → Service →
Repository → Adapter. Không sửa API Contract, schema, seed, auth, IAM hoặc
adapter AI/Transcribe/review của C. Không tạo tài nguyên AWS.

**Theo lựa chọn của người dùng: giữ schema, chặn publish mới nếu chưa chứng
minh được APPROVED.** PostgreSQL hiện không có `APPROVED` trong CHECK status,
cũng không có approval flag/by/at cho Lesson. Vì vậy khóa học DRAFT hiện
không thể vượt qua điều kiện phê duyệt để publish mới. Course đã PUBLISHED
vẫn trả 200 idempotent; đây không phải một lần approve/publish nội dung mới.

LocalProcessor hiện là **hàng đợi yêu cầu development trên đĩa**, không phải
worker transcode hoặc workflow AWS. `202 PROCESSING` chỉ nghĩa request local
đã được nhận; chưa tạo processed video/transcript/AI, chưa tự kết thúc job.

## Thành phần có trước

- Ghi chú snapshot cũ: ví dụ xác thực dùng `X-Demo-User`; không còn là hướng dẫn hiện hành. Backend hiện dùng bearer access token; xem [API contract](../api-contract.md).
- S3 adapter thật: Presigned PUT, HEAD và Presigned GET SigV4; playback service
  có development raw policy và log lỗi an toàn.
- Lesson repository và các cột raw/processed key, status, retry_count,
  error_message, transcript/summary/concepts; Course có DRAFT/PUBLISHED.
- `local_processor.py`, `mediaconvert.py`, review service/router đang là file
  trống. Không có endpoint processing-status/retry/course publish.
- Model Lesson thiếu `AI_PROCESSING` trong CHECK, trong khi schema.sql/DB đã có;
  cả model và DB thiếu `APPROVED` so với draft contract. Không sửa các CHECK này.

## API và ví dụ

Tất cả endpoint dùng identity hiện có; không tạo route bypass xác thực.

| Endpoint | Quyền | Response |
| --- | --- | --- |
| `GET /lessons/{id}/processing-status` | Instructor sở hữu course | 200, trạng thái DB |
| `POST /lessons/{id}/retry` | Instructor sở hữu course hoặc Admin | 202 khi dispatch hợp lệ |
| `POST /courses/{id}/publish` | Instructor sở hữu course | 200, CourseResponse hiện có |

GET status có `Cache-Control: no-store`. Các ví dụ dưới đây chỉ minh họa schema;
không phải kết quả xử lý AWS thật:

```json
{
  "lesson_id": 3,
  "status": "FAILED",
  "retry_count": 1,
  "error_message": "Video processing failed. Please retry or contact support.",
  "updated_at": "2026-10-30T03:00:00Z"
}
```

Không trả nguyên `error_message` trong DB vì có thể chứa exception, signed URL,
credentials hoặc object key. Trạng thái và retry_count là dữ liệu DB thực;
public error là thông điệp an toàn, chỉ xuất hiện ở FAILED.

Retry hợp lệ trả cùng schema với `status=PROCESSING`, `retry_count` tăng 1,
`error_message=null`. Không nhận source key từ frontend. Chỉ lấy raw key từ DB,
HEAD xác minh tồn tại/quyền đọc và object không rỗng trước khi dispatch.

| Lỗi retry | HTTP/code | Thay đổi DB |
| --- | --- | --- |
| Không FAILED | 409 `LESSON_NOT_FAILED` | Không |
| Chưa có raw key | 409 `RAW_VIDEO_REQUIRED` | Không |
| Input mất | 404 `INPUT_VIDEO_NOT_FOUND` | Không |
| Input rỗng | 409 `INVALID_VIDEO_INPUT` | Không |
| S3 từ chối/thiếu credentials/bucket lỗi | 502 `INPUT_STORAGE_UNAVAILABLE` | Không |
| Workflow chưa cấu hình | 503 `WORKFLOW_NOT_CONFIGURED` | Không |
| Local dispatch thất bại | 503 `PROCESSING_DISPATCH_FAILED` | Rollback |
| Course/Lesson đang bị khóa | 409 `PROCESSING_BUSY` | Rollback |

Publish kiểm tra course tồn tại/ownership trước idempotency. Với DRAFT, yêu cầu
có section, mỗi section có Lesson, **mọi Lesson phải APPROVED** và có processed
key. Không coi raw upload, REVIEW_REQUIRED hoặc PUBLISHED từ dữ liệu legacy/seed
là bằng chứng approve cho một Course DRAFT. Thiếu approve trả:

```json
{
  "detail": "Every lesson must be explicitly approved before publishing.",
  "code": "LESSON_APPROVAL_REQUIRED",
  "request_id": "<request-id>"
}
```

Course đã PUBLISHED trả CourseResponse hiện có, ví dụ các trường chính:
`id`, `instructor_id`, `title`, `status="PUBLISHED"`, `created_at`, `updated_at`,
`learning_objectives`, `description`, `sections`. Không sửa timestamps/lesson
khi nhận lại cùng lệnh publish. Nội dung rỗng/sai trạng thái/đang bị khóa trả 409.

## Chuyển trạng thái

| Trạng thái trước | Điều kiện/lệnh | Trạng thái sau | Giai đoạn này |
| --- | --- | --- | --- |
| Bất kỳ | GET status | Giữ nguyên | Đã có |
| FAILED | Raw hợp lệ + S3 HEAD + local dispatch thành công | PROCESSING; count +1; xóa lỗi | Đã có |
| FAILED | Input/adapter/dispatch lỗi | FAILED; giữ count và lỗi cũ | Đã có |
| Khác FAILED | Retry | Giữ nguyên, 409 | Đã có |
| PROCESSING | Transcode/Transcribe/AI/review | Không tự chuyển | Chờ worker/C/workflow |
| APPROVED | Course publish hợp lệ | PUBLISHED, cùng transaction với course | Logic đã có; DB hiện chưa lưu được APPROVED |
| PUBLISHED | Course đã published nhận lại publish | Giữ nguyên | Đã có |

Không triển khai lần submit đầu tiên DRAFT/UPLOADED → PROCESSING; cần thống nhất
EventBridge hay confirm-upload ở giai đoạn sau. Không tự approve bằng local adapter.

## Transaction, concurrency và local dispatch

- Retry/publish khóa theo thứ tự Course → Lesson; publish còn khóa section trước
  danh sách Lesson. Repository dùng `FOR UPDATE NOWAIT` và `populate_existing`
  để không dựa vào ORM object cũ. PostgreSQL lock conflict (`55P03`) → 409.
- Retry kiểm tra lại FAILED dưới khóa, flush update rồi dispatch, commit chỉ khi
  adapter nhận job. Counter và lỗi cũ rollback khi dispatch thất bại.
- `VideoProcessor.start(VideoProcessingRequest)` là interface cho dispatcher
  tương lai. Receipt xác nhận đã nhận, không xác nhận xử lý thành công.
- Idempotency key cố định: `lesson-{id}-retry-{attempt}`. LocalProcessor ghi JSON
  vào file tạm, fsync rồi tạo hard link nguyên tử không ghi đè. Cùng job/payload
  trả lại cùng receipt; payload khác bị từ chối. Không dùng memory lock để giả
  chống concurrent request giữa nhiều Uvicorn worker.
- DB và filesystem không có distributed transaction. Nếu DB commit lỗi sau khi
  manifest đã ghi, manifest có thể còn lại; gọi lại dùng cùng idempotency key.
  Adapter local **không tự chạy manifest**. Worker tương lai phải xác minh trạng
  thái DB PROCESSING và đúng attempt trước khi chạy, xử lý manifest mồ côi.
- Trước external dispatch thật cần transactional outbox hoặc cơ chế reconciliation
  bền vững; không nối thẳng Step Functions rồi coi DB commit là bảo đảm exactly-once.
- Các writer của C/workflow sau này cần dùng cùng lock order hoặc optimistic
  version/attempt guard khi cập nhật kết quả, tránh callback cũ ghi đè retry mới.

Tham khảo: [SQLAlchemy FOR UPDATE NOWAIT](https://docs.sqlalchemy.org/en/20/core/selectable.html#sqlalchemy.sql.expression.Select.with_for_update).

## Cấu hình và chạy thử

Mặc định `VIDEO_PROCESSOR_BACKEND=disabled`; retry FAILED có input trả 503 và
giữ nguyên DB. Development local cần bật rõ trong `.env` gốc rồi restart backend:

```dotenv
APP_ENV=development
VIDEO_PROCESSOR_BACKEND=local
# Mặc định: <repo>/.local-video-jobs, đã gitignore
# LOCAL_VIDEO_JOB_DIR=D:/path/to/local-video-jobs
```

Backend vẫn cần credentials đọc S3 thật để HEAD raw input. Local backend bị chặn
ở production ngay cả khi cấu hình `VIDEO_PROCESSOR_BACKEND=local`.

Ví dụ PowerShell khi backend đang chạy, dùng identity hợp lệ:

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/lessons/8/processing-status' -Headers @{ Authorization = "Bearer $localAccessToken" }
Invoke-RestMethod -Method Post 'http://127.0.0.1:8000/lessons/8/retry' -Headers @{ Authorization = "Bearer $localAccessToken" }
Invoke-RestMethod -Method Post 'http://127.0.0.1:8000/courses/2/publish' -Headers @{ Authorization = "Bearer $localAccessToken" }
```

Lesson 8 hiện PUBLISHED, nên retry phải trả 409; không sửa dữ liệu bài này để
demo thành công. Course 2 hiện PUBLISHED, nên publish trả 200 idempotent.

## Kiểm thử và kết quả thực tế

Chạy từ `backend` (cài `requirements-dev.txt` khi thiếu httpx):

```powershell
../.venv/Scripts/python.exe -m unittest discover -s tests/unit -p 'test_*.py' -v
$env:LEARNCLOUD_RUN_DB_TESTS = '1'
../.venv/Scripts/python.exe -m unittest discover -s tests/integration -p 'test_video_processing_db.py' -v
```

Integration test dùng DB hiện có, outer transaction + savepoint; fixture update
được rollback, không commit fixture/schema/seed. Các kết nối PostgreSQL độc lập
thực sự tranh khóa để kiểm tra retry/publish concurrent. S3 HEAD được stub;
local queue dùng thư mục tạm thật, không tạo AWS resource.

- **66/66 unit/regression pass**: gồm status/quyền, retry,
  publish approval gate, local filesystem lỗi, concurrent local dispatch, commit
  failure/replay và S3 GET/PUT API SigV4.
- **9/9 integration PostgreSQL pass**: rollback dispatch, duplicate retry, khóa
  course/lesson bằng hai connection, idempotent publish và chặn draft thiếu approve.
- HTTP thật: Lesson 8 status **200 PUBLISHED**, retry **409 LESSON_NOT_FAILED**;
  Course 2 publish **200 PUBLISHED** (idempotent); identity không tồn tại **401**.
- Không xác minh workflow AWS/MediaConvert/Transcribe/AI hoặc tạo video output.
  Test publish với APPROVED là **unit fixture cho logic tương lai**, không phải
  tuyên bố schema hiện tại đã hỗ trợ approval.

## File thay đổi

| Nhóm | File |
| --- | --- |
| API | `backend/app/api/lessons.py`, `backend/app/api/courses.py` |
| Schema response | `backend/app/schemas/lesson.py` |
| Services | `backend/app/services/processing_service.py` (mới), `lesson_service.py`, `course_service.py` |
| Repositories | `backend/app/repositories/lessons_repo.py`, `courses_repo.py` |
| Adapters | `backend/app/adapters/video/base.py` (mới), `local_processor.py`, `backend/app/adapters/storage/s3_storage.py` |
| Config | `backend/app/config.py`, `.env.example`, `.gitignore` |
| Tests | `backend/tests/unit/test_video_processing.py` (mới), `test_lesson_video_url.py`, `backend/tests/integration/test_video_processing_db.py` (mới) |
| Test dependencies | `backend/requirements-dev.txt` (mới) |
| Báo cáo | `docs/video-processing-phase1.md` (mới) |

## Bàn giao giai đoạn tiếp theo

1. Thống nhất với C/schema owner trạng thái APPROVED và semantics approve/publish;
   đồng bộ model/SQL/migration trước khi mở publish mới. C sở hữu review/AI.
2. Chốt nguồn submit đầu tiên: EventBridge hoặc confirm-upload; lọc bucket/key,
   xác thực event, deduplicate và kiểm soát object version/ETag.
3. Thêm outbox/job persistence, execution ID/attempt, callback guards và recovery
   cho crash; thiết kế retry terminal state và giới hạn theo policy nhóm.
4. Cài dispatcher Step Functions và MediaConvert thực, cấu hình job template/output
   keys, xử lý completed/failed events. Không coi local manifest là workflow AWS.
5. Nối handoff C cho Transcribe/AI rồi REVIEW_REQUIRED, không tự sinh nội dung giả.
6. B tích hợp polling/status/retry/publish dựa trên schema và mã lỗi; không coi
   202 hoặc PROCESSING là video đã sẵn sàng/phê duyệt.
