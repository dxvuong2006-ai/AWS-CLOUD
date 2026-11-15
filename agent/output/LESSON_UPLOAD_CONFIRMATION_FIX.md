# Sửa upload video Lesson: xác nhận, metadata và chống trùng

Ngày 10/11/2026. Giữ các thay đổi hiển thị chưa commit từ lần trước; bổ sung phần upload/persistence còn thiếu. Không xóa/ghi object S3, không chạy migration/DML trên RDS, không sửa `.env`, JWT, IAM/CORS hoặc hạ tầng AWS trong công việc này.

## 1. Nguyên nhân đã xác định

Luồng cũ là **Frontend xin URL → PUT trực tiếp S3 → coi thành công**. Frontend không gọi xác nhận. Khi `VIDEO_PIPELINE_ENABLED=false`, `UploadService` không tạo `video_uploads`, không lưu `lessons.raw_video_key` và không đổi trạng thái. Mỗi request xin URL sinh UUID/key mới; Lesson vẫn DRAFT nên lần sau vẫn upload được. Sửa nhãn hiển thị ở lần trước không giải quyết được thiếu metadata này.

Khi pipeline bật, intent được lưu và EventBridge claim mới gắn RAW/đưa Lesson sang PROCESSING. Luồng đó trước đây vẫn cho nhiều intent cùng một Lesson trước khi có claim; cơ chế first-claim-wins ngăn nhiều job nhưng không ngăn nhiều RAW không chủ đích.

Đã xác minh bằng truy vấn **read-only=on** vào database hiện tại:

- Pipeline hiện **false**, processor **disabled**.
- Lesson **9, 10, 13, 14, 15**: DRAFT, không có RAW/processed key và không có upload intent.
- `video_uploads` có intent cho Lesson **11, 12**, mỗi Lesson một dòng; hai Lesson này đang PROCESSING.
- HEAD một RAW đã liên kết của Lesson 6 thành công, Content-Type video/mp4. Không đọc nội dung file.
- **ListObjectsV2 và GetBucketCors bị AccessDenied** bằng credentials kiểm tra hiện tại. Vì vậy chưa xác định số/key RAW chưa liên kết của các Lesson DRAFT; việc người dùng thấy các file đó trên S3 chưa được đối chiếu độc lập qua API. Không tự chọn file cũ để gắn vào database.

## 2. Luồng mới

1. `POST /lessons/{id}/upload-url`: xác thực Instructor, kiểm owner, khóa Course rồi Lesson bằng PostgreSQL `FOR UPDATE NOWAIT`.
2. Kiểm tra chưa có video hiện hành, Lesson/Course còn DRAFT, không đang retry/xử lý. Dùng ledger `video_uploads` **cho cả hai chế độ pipeline**.
3. Nếu chưa có intent, kiểm tra prefix S3 `lessons/{id}/raw/` để phát hiện RAW cũ không được ghi DB. Có object thì trả `409 UNLINKED_RAW_VIDEO`; không có quyền kiểm tra thì trả `502 UPLOAD_INVENTORY_UNAVAILABLE`. Không cấp key mới khi chưa xác minh được.
4. Lưu một intent trước khi trả URL. Request retry cùng loại/kích thước dùng lại **upload_id và key cũ**, kể cả cần gia hạn URL; không sinh file thứ hai. Payload khác trả 409. Nhiều intent lịch sử trả lỗi yêu cầu review.
5. PUT luôn ký và gửi `If-None-Match: *`, ngăn ghi đè cùng key. [AWS conditional writes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html)
6. **API mới:** `POST /lessons/{id}/confirm-upload`, body chỉ `{ "upload_id": "<32 hex>" }`. Server tìm đúng intent/lesson/owner, kiểm key identity, HEAD S3 và đối chiếu kích thước, MIME, ETag, thời gian ghi trong cửa sổ được cấp. Không tin object_key do client khai báo.
7. Chỉ sau xác minh mới gắn RAW vào Lesson. Pipeline tắt: trạng thái UPLOADED/chờ xử lý. Pipeline bật: giữ DRAFT có RAW để EventBridge hiện có tiếp tục claim; confirmation không khởi chạy job. Nếu event đã đưa Lesson sang PROCESSING/READY/FAILED, confirm không đưa lùi trạng thái.

Không có thay đổi schema/migration mới: tái sử dụng ledger hiện có của migration 0005. Nếu database khác chưa có ledger thì upload dừng với 503; operator phải review schema, không bật lại nhánh upload không lưu metadata. Không replay migration 0005/0004 tùy tiện vì xung đột lịch sử đã ghi trong audit trước.

## 3. Đồng bộ UI và bảo vệ video hiện hành

- Frontend chỉ báo hoàn tất sau confirm thành công, hiển thị “Đang xác nhận với Backend” sau PUT. Backend cũ thiếu upload_id/conditional header bị chặn trước khi gửi file.
- PUT 409/412 hoặc mất response được xử lý bằng confirm **cùng upload ID**; không tự cấp key khác. Nếu file chưa có trên S3 thì tiếp tục đúng lượt upload đang dở.
- List/detail/processing-status cùng trả metadata `video_status`; có thêm `UPLOAD_PENDING`, `upload_pending`, `pending_upload_id` cho lượt đã cấp nhưng chưa xác nhận. Không coi intent đơn thuần là RAW đã upload.
- Khi mở lại trang có pending ID, UI xác nhận lại file cũ trước. File tồn tại/đúng metadata thì phục hồi trạng thái, không hiện upload mới; HEAD báo chưa có object thì chỉ cho **tiếp tục cùng lượt**. Lỗi xác minh/intent mơ hồ không mở đường cấp một video mới.
- Lesson đã có RAW/processed hoặc đang xử lý/ready/failed không được cấp upload mới, kể cả cố gửi request ngoài UI. Link “Tải video khác” gây hiểu nhầm đã được bỏ. Hiện chưa triển khai chức năng thay thế; cần một workflow riêng có xác nhận nếu nhóm yêu cầu sau này.
- Retry xử lý thất bại tiếp tục dùng video hiện hành và endpoint retry cũ. Pipeline đang disabled vẫn trả lỗi workflow chưa cấu hình; bản sửa không tự bật pipeline hoặc tạo job giả.
- Event cũ trỏ tới RAW khác không được thay video đã gắn; confirmation không xóa output, transcript, summary hay quan hệ Lesson.

## 4. Hai điều kiện triển khai cần nhóm xử lý

**Quyền AWS:** preflight chống RAW mồ côi cần `s3:ListBucket` giới hạn prefix RAW của ứng dụng; confirm cần quyền HEAD/GetObject. Credentials kiểm tra hiện tại có HEAD nhưng không có ListBucket, nên **upload mới lần đầu có thể bị chặn an toàn** cho tới khi AWS owner xác nhận/cấp đúng quyền cho runtime. Không tự sửa IAM trong công việc này. Browser cần CORS cho PUT và header `If-None-Match`; GetBucketCors bị từ chối nên chưa xác nhận cấu hình thực tế. [AWS CORS matching](https://docs.aws.amazon.com/AmazonS3/latest/userguide/cors.html)

**RAW cũ chưa ghi DB:** deploy code không tự sửa các file cũ và không tự chọn giữa nhiều RAW. Cần xác nhận Lesson ID, instructor ID và **đúng một key** muốn giữ làm video hiện hành. Không upload lại để chữa metadata, không xóa các RAW còn lại. Đã chuẩn bị công cụ phục hồi có preview cho operator được ủy quyền ở phần dưới; **chưa chạy trên RDS**.

## 5. Phục hồi RAW cũ sau khi được phê duyệt

Công cụ: `backend/scripts/attach_existing_raw_video.py`. Chỉ chấp nhận Lesson/Course trống còn DRAFT, đúng owner đã duyệt, key đúng prefix/UUID của Lesson, HEAD hợp lệ và chưa có intent/video hiện hành. Không dùng ListBucket, không upload lại, không ghi đè dữ liệu đã có. DB operator phải được DBA cấp membership `learncloud_video_metadata_operator`; app user/Instructor token không thể tự cấp quyền này.

DBA review và chuẩn bị riêng trên môi trường được phép; các lệnh minh họa sau **không được agent thực thi trên RDS**:

```sql
CREATE ROLE learncloud_video_metadata_operator NOLOGIN;
-- DB login cá nhân của operator được DBA tạo/password qua kênh riêng.
GRANT learncloud_video_metadata_operator TO <operator_login>;
GRANT CONNECT ON DATABASE learncloud TO learncloud_video_metadata_operator;
GRANT USAGE ON SCHEMA public TO learncloud_video_metadata_operator;
GRANT SELECT ON public.lessons,public.sections,public.courses,public.video_uploads
    TO learncloud_video_metadata_operator;
GRANT UPDATE(raw_video_key,status,updated_at) ON public.lessons TO learncloud_video_metadata_operator;
-- Cần quyền UPDATE một cột để lấy row lock Course; công cụ không sửa Course.
GRANT UPDATE(updated_at) ON public.courses TO learncloud_video_metadata_operator;
GRANT INSERT ON public.video_uploads TO learncloud_video_metadata_operator;
```

Kiểm tra role tồn tại/quyền hiện có trước khi DBA chạy; không tạo/grant lại mù quáng. Sau backup, xác nhận đối tượng và phê duyệt, dùng terminal tin cậy tại root repository:

```powershell
$recoveryArgs = @(
  '--lesson-id', '<LESSON_ID>',
  '--expected-instructor-id', '<INSTRUCTOR_ID>',
  '--object-key', 'lessons/<LESSON_ID>/raw/<UUID_32_HEX>.mp4',
  '--operator-db-user', '<OPERATOR_LOGIN>',
  '--approval-reference', '<MA_PHE_DUYET>'
)
.\.venv\Scripts\python.exe backend/scripts/attach_existing_raw_video.py @recoveryArgs
# Chỉ sau khi preview đúng file/người sở hữu và được phê duyệt:
.\.venv\Scripts\python.exe backend/scripts/attach_existing_raw_video.py @recoveryArgs --apply
```

Mặc định connection DB read-only; password DB nhập ẩn, không đổi DATABASE_URL. `--apply` yêu cầu nhập đúng `ATTACH <LESSON_ID>`, kiểm lại owner/trạng thái/ETag rồi dùng cùng hàm confirm để gắn metadata. Bảo toàn ID/title/Section/Course và file S3. Công cụ không thay video đã gắn và từ chối chạy lần hai. Khi pipeline bật, file cũ có thể cần AWS owner review/replay event cũ để bắt đầu xử lý; công cụ không tự dispatch workflow.

## 6. Kiểm thử

- **118 test Backend pass, 6 subtests pass**: upload/confirmation, metadata trạng thái, Authorization P0 và pipeline regression, trong môi trường offline chặn network.
- **6 test PostgreSQL riêng pass**: hai request đồng thời thật, NOWAIT conflict, retry cùng một key, confirm ghi đúng RAW, chặn fresh upload, guard từ chối URL RDS/tunnel và công cụ recovery preview/confirmation/apply một lần. Test S3 dùng doubles, không tạo/xóa object AWS.
- **64 test Frontend pass**, build pass. Còn warning react-router/chunk lớn như trước.
- Chưa chạy upload end-to-end bằng browser lên S3 thật hoặc recovery trên RDS. Read-only kiểm tra quyền đã được nêu rõ; không khẳng định đã giải quyết IAM/CORS hoặc tự phục hồi file cũ.

Lệnh test offline:

```powershell
.\.venv\Scripts\python.exe backend/tests/run_auth_offline.py backend/tests/unit/test_upload_confirmation.py backend/tests/unit/test_lesson_video_status.py backend/tests/unit/test_video_pipeline.py backend/tests/unit/test_video_pipeline_migration.py backend/tests/unit/test_authorization_p0.py
Set-Location frontend
npm.cmd test
npm.cmd run build
```

Test PostgreSQL chỉ dùng `LEARNCLOUD_RUN_UPLOAD_DB_TESTS=1` và `LEARNCLOUD_UPLOAD_TEST_DATABASE_URL` trỏ `127.0.0.1:55439/learncloud_auth_test` với user test cùng tên, schema đã chuẩn bị. Không dùng DATABASE_URL ứng dụng/RDS làm test target. Cluster test đã được dừng sau khi hoàn tất.

## 7. File thay đổi

| File | Nội dung |
|---|---|
| `backend/app/services/upload_service.py` | Reservation bền vững, row locks, inventory guard, confirm, resume một key |
| `backend/app/api/uploads.py` | API confirm và payload cấm field ngoài hợp đồng |
| `backend/app/adapters/storage/s3_storage.py` | Kiểm tra RAW prefix chỉ đọc, không xóa/ghi object |
| `backend/app/services/video_pipeline_service.py` | Giữ dispatcher; chặn event khác thay video hiện hành |
| `backend/app/lesson_video_state.py`, `backend/app/schemas/lesson.py` | Metadata trạng thái chờ upload/confirm |
| `backend/app/services/screen_workflows.py`, `backend/app/services/processing_service.py` | Đồng bộ pending metadata vào response |
| `backend/app/api/lessons.py`, `backend/app/api/courses.py` | List/detail cùng pending metadata |
| `frontend/src/api/uploads.api.js` | PUT rồi confirm; không thành công giả; phục hồi mất response |
| `frontend/src/pages/VideoUploadPage.jsx` | Không upload mới khi đã có/pending; xác nhận lại/resume/retry rõ ràng |
| `frontend/src/utils/lessonVideoStatus.js` | Nhãn UPLOAD_PENDING dùng chung danh sách/trang upload |
| `backend/scripts/attach_existing_raw_video.py` — mới | Preview/recovery có kiểm quyền cho RAW cũ |
| `backend/tests/unit/test_upload_confirmation.py` — mới | HTTP, JWT, owner, S3 validation, legacy orphan guard |
| `backend/tests/integration/test_upload_confirmation_pg.py` — mới | Concurrency PostgreSQL và recovery CLI |
| `backend/tests/unit/test_video_pipeline.py` | Cập nhật contract ledger bắt buộc, giữ pipeline tests |
| `backend/tests/unit/test_lesson_video_status.py` | Dùng error handlers thật trong fixture |
| `frontend/tests/uploads.test.cjs`, `frontend/tests/lesson-video-status.test.cjs` | Confirm, conditional PUT, pending state, retry |

`CourseEditorPage.jsx`, `schemas/course.py`, `api/screen_workflows.py` và các file read model từ lượt trước vẫn giữ nguyên thay đổi hiển thị; không revert. Triển khai Backend và Frontend cùng phiên bản, kiểm tra ledger/quyền trước khi thử upload. Không cần sửa JWT hay `.env` để chữa nguyên nhân thiếu confirm.
