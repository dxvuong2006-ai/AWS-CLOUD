# Sửa trạng thái video trong danh sách Lesson

Ngày 10/11/2026. Không chạy migration/DML, không sửa dữ liệu RDS, cấu hình AWS, `.env` hoặc cơ chế xử lý video.

## Nguyên nhân và đường đi dữ liệu

- Danh sách trong `CourseEditorPage.jsx` gọi `management.api.getCourse` → `GET /instructor/courses/{id}` → `screen_workflows.course_detail`. API này có `lesson.status` nhưng không có thông tin video RAW/processed. Frontend gán thẳng **`DRAFT` = “Chưa có video”**, dù DRAFT là trạng thái lesson, không đủ phân biệt video đã được gắn hay chưa.
- Trang theo dõi `VideoUploadPage.jsx` lấy `GET /lessons/{id}/processing-status` mỗi 5 giây. Danh sách trước đây chỉ tải một snapshot lúc mở trang; nếu event upload/pipeline đổi DRAFT sang PROCESSING sau đó, danh sách có thể giữ nhãn cũ trong khi trang chi tiết đã đọc trạng thái mới.
- Các đường API khác cũng thiếu contract nhất quán: `GET /sections/{id}/lessons`, `GET /lessons/{id}` dùng `LessonResponse` không có status; nested lesson của `/courses/instructor/me` dùng `CourseLessonResponse` cũng loại bỏ status khi serialize.
- Không có cơ sở để coi thiếu processed URL là chưa upload: URL phát video và trạng thái xử lý là hai thông tin khác nhau.

Đã đọc metadata tổng hợp từ database đang cấu hình bằng transaction **read-only=on**, không đọc key video hay dữ liệu user. Có 2 lesson PROCESSING với cả metadata RAW và processed, cùng các lesson PUBLISHED chưa có processed key. Không ghi/chỉnh các bản ghi này. Đây là xác nhận metadata thực tế, không phải kiểm chứng S3 object. Không xác định được snapshot/lesson ID cụ thể đã hiển thị trong browser của người dùng; lỗi contract và khả năng snapshot cũ đã được tái hiện bằng test.

## Thay đổi

Backend dùng chung read model `LessonVideoFields`, giữ nguyên `status` đã lưu và thêm các field response **`video_status`**, **`has_raw_video`**, **`has_processed_video`**. Đây là field tính khi đọc, không phải cột/migration mới. Không trả raw/processed key, presigned URL hay thông báo lỗi AWS trong metadata này.

| `video_status` | Quy tắc Backend | Hiển thị |
|---|---|---|
| `NOT_UPLOADED` | DRAFT, không có RAW hoặc processed key | Chưa có video |
| `UPLOADED` | UPLOADED; hoặc DRAFT đã có RAW key | Đã upload RAW / Chờ xử lý |
| `PROCESSING` | PROCESSING / TRANSCRIBING / AI_PROCESSING | Đang xử lý, kèm bước tương ứng |
| `READY` | REVIEW_REQUIRED / PUBLISHED; hoặc DRAFT có processed key | Video sẵn sàng, phân biệt chờ duyệt/đã publish |
| `FAILED` | FAILED, kể cả còn artifact cũ | Xử lý thất bại |
| `UNKNOWN` | Thiếu/trạng thái không được nhận diện | Chưa xác định trạng thái video |

FAILED/đang xử lý có ưu tiên hơn sự tồn tại processed artifact. Trạng thái READY phản ánh metadata/trạng thái Backend, không tự xác nhận file S3 phát được. Không thay trạng thái trong database hoặc tự tiến pipeline.

Các API quản trị, danh sách section, lesson detail và processing-status dùng cùng quy tắc. Frontend chỉ hiển thị `video_status` Backend trả về; thiếu field thì hiện UNKNOWN, không đoán từ URL hoặc mặc định DRAFT. Lesson DRAFT đã có RAW dẫn tới **Xem trạng thái**, không còn mời upload như lesson trống.

Danh sách refresh mỗi 5 giây khi còn lesson chưa kết thúc, gồm snapshot DRAFT để bắt event upload đến trễ; refresh thêm khi focus/hiện lại tab. Không polling khi tab ẩn, không gửi chồng request và không ghi đè form chưa lưu. Response của request cũ bắt đầu trước thao tác sửa cũng bị loại bỏ. API course quản trị thêm `Cache-Control: no-store`.

## File sửa/thêm

| File | Nội dung |
|---|---|
| `backend/app/lesson_video_state.py` — mới | Phân loại trạng thái video chỉ đọc |
| `backend/app/schemas/lesson.py` | Read model dùng chung; bổ sung response list/detail/processing |
| `backend/app/schemas/course.py` | Nested lesson giữ cùng metadata trạng thái |
| `backend/app/services/screen_workflows.py` | Trả metadata cho danh sách lesson quản trị |
| `backend/app/services/processing_service.py` | Chỉ sửa phần serialize response, không sửa retry/dispatch/state transitions |
| `backend/app/api/screen_workflows.py` | No-store cho course quản trị |
| `frontend/src/utils/lessonVideoStatus.js` — mới | Nhãn/màu/action và điều kiện refresh theo trạng thái Backend |
| `frontend/src/pages/CourseEditorPage.jsx` | Bỏ DRAFT=chưa có video; refresh không mất form edits |
| `frontend/src/pages/VideoUploadPage.jsx` | Dùng cùng cách hiển thị; phân biệt RAW chờ xử lý |
| `backend/tests/unit/test_lesson_video_status.py` — mới | 16 test HTTP/serializer/quyền/metadata không đổi |
| `frontend/tests/lesson-video-status.test.cjs` — mới | 6 test phân loại hiển thị, URL độc lập và refresh |

## Kết quả kiểm thử

- **16 test mới Backend pass:** so sánh cùng một lesson qua 6 API; DRAFT trống/RAW/processed, mọi bước xử lý, sẵn sàng, thất bại, unknown, whitespace, quyền owner, refresh sau thay đổi. Các lần đọc không đổi metadata Lesson và không gọi AWS.
- **99 test Backend pass**, thêm **6 subtests pass**, khi chạy cùng Authorization P0, pipeline, migration preflight và learning contract trong môi trường offline chặn socket. Không hạ guard để test pass.
- **58 test Frontend pass**, trong đó 6 test mới; `npm.cmd run build` pass. Còn warning react-router `use client`/chunk lớn như trước.
- `git diff --check` pass. Chưa kiểm thử trực tiếp browser đang mở của người dùng hoặc upload mới lên AWS; không phát sinh S3 PUT, thay pipeline hay RDS DML.

Lệnh kiểm thử:

```powershell
.\.venv\Scripts\python.exe backend/tests/run_auth_offline.py backend/tests/unit/test_lesson_video_status.py backend/tests/unit/test_authorization_p0.py backend/tests/unit/test_video_pipeline.py backend/tests/unit/test_video_pipeline_migration.py backend/tests/unit/test_learning_contract.py
Set-Location frontend
npm.cmd test
npm.cmd run build
```

Khởi động lại Backend để nạp response mới và restart/rebuild Frontend để dùng nhãn mới; không cần đổi `.env` hoặc migration. Nếu chỉ có PUT lên S3 thành công nhưng Backend hoàn toàn chưa ghi nhận RAW key hay trạng thái upload/event, bản sửa này không tự tạo bằng chứng upload hoặc kích hoạt pipeline: UI phải phản ánh metadata Backend thực có, không suy đoán từ state tạm của browser.
