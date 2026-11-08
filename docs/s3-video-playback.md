# Phát MP4 từ S3 private trên LearnCloud

## Cập nhật chẩn đoán Lesson 8 sau khi gắn raw key

- Đã xác minh repository đọc `raw_video_key=lessons/8/raw/sample.mp4`,
  `processed_video_key=NULL`, status published từ DB `learncloud` tại
  `localhost:5434`, schema `public`; user instructor 1 có quyền Lesson 8.
- Nguyên nhân `VIDEO_NOT_AVAILABLE`: `.env` local thiếu `APP_ENV` và
  `ALLOW_RAW_VIDEO_PLAYBACK`. Settings vì thế dùng mặc định production/false;
  service chặn raw trước khi gọi S3. File `.env` được đọc đúng từ gốc repo,
  không phải lỗi đường dẫn, model, repository hay DB.
- Đã bổ sung `APP_ENV=development`, `ALLOW_RAW_VIDEO_PLAYBACK=true` vào `.env`
  local (file được gitignore). Không đổi mặc định production hoặc logic service.
  Settings được khởi tạo khi import; phải restart backend để nhận cấu hình mới.
- **25/25 test pass**, bao gồm đọc dotenv, biến môi trường ghi đè dotenv,
  production chặn raw và regression ký PUT không HEAD. Vite build pass.
- Integration với DB thật và HTTP trên backend mới: Lesson 8 metadata **200**,
  video-url của user 1 **502 VIDEO_STORAGE_UNAVAILABLE**, user không tồn tại **401**.
  Raw đã vượt qua bước chọn key; S3 HEAD thật gặp **NoCredentialsError**.
- Phiên chạy hiện không có `AWS_PROFILE`, không có profile khả dụng và boto3
  không tìm thấy credentials. Cần cấu hình AWS profile/credentials cho đúng
  user chạy backend, đặt `AWS_PROFILE` trong **môi trường tiến trình** trước
  khi chạy uvicorn. Chỉ thêm `AWS_PROFILE` vào `.env` của Pydantic không tự
  xuất nó sang boto3; Settings hiện không khai báo trường này.
- Chưa đạt HTTP 200 playback, chưa xác minh Presigned GET/range hoặc phát/tua
  từ S3 thật. Browser connector hiện báo `The browser access host is unavailable`.
  Frontend route phục vụ HTML 200 chỉ chứng minh Vite phục vụ route.

Phần kết quả triển khai ban đầu ở cuối tài liệu là snapshot trước khi Lesson 8
được gắn key; cập nhật này thay thế các kết luận về dữ liệu/credentials/test hiện tại.

Luồng đã triển khai: LearningPage lấy metadata như trước, sau đó gọi
`GET /lessons/{lesson_id}/video-url` bằng API client hiện có. API dùng
`get_current_user` → `lesson_service.get_video_url_for_user` →
`get_lesson_for_user` → `lessons_repo`. Sau khi xác minh quyền, S3 adapter
thực hiện `HeadObject`, rồi tạo Presigned GET bằng boto3 với Signature V4.
Frontend truyền `video_url` qua prop `src` của HTML5 VideoPlayer.

## File thay đổi

| File | Thay đổi |
| --- | --- |
| `.env.example` | Cấu hình bucket đúng tên, development/raw/TTL với mặc định an toàn |
| `backend/app/config.py` | Đọc môi trường và cờ raw, kiểm tra giới hạn TTL |
| `backend/app/adapters/storage/s3_storage.py` | SigV4, HEAD object, ký Presigned GET |
| `backend/app/api/lessons.py` | Route video-url, identity dependency, schema Swagger, no-store |
| `backend/app/services/lesson_service.py` | Dùng repository/quyền hiện tại, chọn key DB, ánh xạ lỗi S3 |
| `backend/app/schemas/lesson.py` | Response gồm bốn trường playback |
| `backend/requirements-dev.txt` | Dependency httpx để chạy test API offline |
| `backend/tests/unit/test_lesson_video_url.py` | 21 test API/service/S3 signing |
| `frontend/src/api/client.js` | Truyền mã lỗi và tùy chọn cache |
| `frontend/src/api/lessons.api.js` | Request URL live; bỏ qua hoàn toàn khi mock |
| `frontend/src/hooks/useLesson.js` | Chặn response Lesson cũ khi chuyển bài |
| `frontend/src/hooks/useLessonVideo.js` | State video độc lập, deduplicate request, kiểm tra hết hạn |
| `frontend/src/pages/LearningPage.jsx` | Nối URL vào player, không chờ Progress |
| `frontend/src/components/learning/VideoPlayer.jsx` | HTML5 playback, loading/lỗi/trống, refresh và khôi phục vị trí |
| `frontend/tests/lessons.api.test.cjs` | 4 test API frontend, gồm mock độc lập với S3 |
| `docs/s3-video-playback.md` | Danh sách file, hướng dẫn và kết quả kiểm thử |

Repository `backend/app/repositories/lessons_repo.py` được tái sử dụng nguyên
trạng; không cần query mới hay thay đổi schema để đọc hai cột key hiện có.

## Cấu hình development

Trong `.env` ở gốc repo, sử dụng đúng tên cấu hình backend:

```dotenv
S3_BUCKET=learncloud-videos-mentorcloud
AWS_REGION=ap-southeast-1
APP_ENV=development
ALLOW_RAW_VIDEO_PLAYBACK=true
VIDEO_URL_EXPIRES_IN=900
```

Khởi động lại backend sau khi đổi cấu hình. `processed_video_key` luôn được
ưu tiên. Chỉ dùng `raw_video_key` khi chưa có processed key và **cả hai** điều
kiện development + cờ raw đều được bật. Mặc định `APP_ENV=production`, cờ raw
`false`; production không dùng raw ngay cả khi cờ được bật riêng lẻ.
Endpoint hiện hỗ trợ object key có đuôi `.mp4` (không phân biệt hoa thường).
Không fallback âm thầm sang raw khi processed object bị mất hoặc bị cấm.

Cấp credentials qua credential provider chain có sẵn của boto3, chẳng hạn
AWS profile được cấu hình trên máy hoặc IAM role của backend. Có thể chọn
profile bằng biến môi trường `AWS_PROFILE` trước khi chạy backend. Không
đưa access key/secret vào source, frontend hoặc tài liệu. Identity chạy
backend cần quyền đọc object (`s3:GetObject`, dùng cho cả HEAD và GET);
object mã hóa SSE-KMS còn cần quyền KMS tương ứng. Giữ bucket private.

Hướng dẫn ký URL: [Boto3 Presigned URLs](https://docs.aws.amazon.com/boto3/latest/guide/s3-presigned-urls.html).
`HeadObject` có thể trả 403 cho cả object không tồn tại nếu identity không
có quyền `s3:ListBucket`; vì vậy không suy diễn 403 thành “object bị mất”.
Tham khảo [AWS HeadObject](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/head_object.html).

Trong `frontend/.env`:

```dotenv
VITE_USE_MOCK=false
VITE_API_URL=http://127.0.0.1:8000
```

API client dùng `VITE_API_URL`, không phải `VITE_API_BASE_URL`. Nếu bỏ cấu hình
URL, mặc định vẫn là `http://127.0.0.1:8000`. Khởi động lại Vite sau khi đổi env.
Với `VITE_USE_MOCK=true`, trang dùng `videoUrl` của mock hiện có và không gọi
endpoint video-url, không cần S3/credentials.

## Kiểm thử Lesson 8

1. Kiểm tra dữ liệu bằng truy vấn **chỉ đọc**:

   ```sql
   SELECT l.id, l.raw_video_key, l.processed_video_key, s.course_id,
          c.instructor_id, c.status AS course_status
   FROM lessons l
   JOIN sections s ON s.id = l.section_id
   JOIN courses c ON c.id = s.course_id
   WHERE l.id = 8;
   ```

   Để thử luồng thành công, Lesson 8 phải được gắn sẵn key của MP4 tồn tại
   trong bucket. Việc gắn key/upload/confirm-upload không thuộc thay đổi này.
   Key không được gửi từ frontend hay query parameter của endpoint playback.

2. Chạy backend từ thư mục gốc repo:

   ```powershell
   Set-Location backend
   ../.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

3. Mở `http://127.0.0.1:8000/docs`, chọn
   `GET /lessons/{lesson_id}/video-url`, **Try it out** → `lesson_id=8` →
   `X-Demo-User=1` (instructor sở hữu course trong DB hiện tại) → **Execute**.
   Với dữ liệu và AWS hợp lệ, kỳ vọng `200` và bốn trường:
   `lesson_id`, `video_url`, `expires_in`, `content_type=video/mp4`.
   Response thành công có `Cache-Control: no-store`.
   Không lưu URL vào file, database hoặc log.

4. Có thể kiểm tra HTTP/range từ PowerShell, không in URL:

   ```powershell
   $playback = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/lessons/8/video-url' -Headers @{ 'X-Demo-User' = '1' }
   $playback | Select-Object lesson_id, expires_in, content_type
   curl.exe --silent --show-error --range 0-1023 --output NUL --write-out '%{http_code}' $playback.video_url
   Remove-Variable playback
   ```

   Kỳ vọng GET range trả `206`; kiểm tra `Content-Range` trong Network của
   browser khi tua. URL được ký cho GET, không dùng `curl -I` (HEAD) để thử nó.

5. Chạy `npm.cmd run dev` trong `frontend`, mở
   `http://127.0.0.1:5173/courses/2/lessons/8`. Bấm phát, tua tới vị trí chưa
   buffer, kiểm tra MP4 phát được. Trang học không chờ Progress; Progress
   vẫn tắt theo code hiện tại. Transcript thiếu/sai cấu trúc được panel hiện
   có xử lý riêng. Không có transcript vẫn phải xem được video.

6. Để thử refresh, đặt `VIDEO_URL_EXPIRES_IN=60` và restart backend. Mở lại
   trang, phát rồi pause; chờ URL hết hạn và tiếp tục phát hoặc tua. Network
   phải có request video-url mới; player giữ vị trí/tốc độ và tiếp tục phát
   khi có thể. Lỗi media được tự thử cấp URL mới tối đa một lần cho một lần
   lỗi liên tiếp, sau đó hiển thị nút thử lại. URL chỉ ở React memory, không
   persist vào storage; mỗi request video-url dùng `cache: no-store`.

Dependency nhận diện người dùng hiện tại là `X-Demo-User`, mặc định ID 1.
Endpoint mới kế thừa đúng dependency và quyền hiện tại: instructor sở hữu
course hoặc student đã enroll vào course published. Đây vẫn là cơ chế demo,
chưa phải xác thực JWT cho production; thay đổi này không sửa login/JWT
hoặc thêm quy tắc unlock mới.

## Trạng thái và lỗi

| HTTP | Code | Ý nghĩa |
| --- | --- | --- |
| 200 | — | URL GET tạm thời và `content_type=video/mp4` |
| 401/403 | Code lỗi chung hiện có | Không có identity hợp lệ/không có quyền Lesson |
| 404 | `NOT_FOUND` | Lesson/section/course không tồn tại |
| 404 | `VIDEO_NOT_AVAILABLE` | Chưa có key được phép phát; UI “Chưa có video” |
| 404 | `VIDEO_OBJECT_NOT_FOUND` | S3 báo object không tồn tại |
| 409 | `VIDEO_FORMAT_UNSUPPORTED` | Key được chọn không phải MP4 |
| 502 | `VIDEO_STORAGE_ACCESS_DENIED` | S3 HEAD từ chối quyền của backend |
| 502 | `VIDEO_STORAGE_UNAVAILABLE` | Thiếu credentials, lỗi kết nối/ký URL hoặc S3 khác |

Không trả exception AWS, credentials hoặc object key trong lỗi. HEAD thành
công chưa bảo đảm browser giải mã được codec bên trong MP4, cũng chưa bảo
đảm quyền GET/KMS vẫn còn hiệu lực sau khi cấp URL; cần kiểm tra phát thật.

## Kiểm thử tự động

Backend dùng unittest có sẵn của Python và httpx ASGITransport, không gọi AWS:

```powershell
Set-Location backend
../.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
../.venv/Scripts/python.exe -m unittest discover -s tests/unit -p test_lesson_video_url.py -v
```

Frontend dùng Node built-in test runner; VM Modules cần flag experimental:

```powershell
Set-Location frontend
node --experimental-vm-modules --test tests/lessons.api.test.cjs
npm.cmd run build
```

## Kết quả thực tế ngày 29/10/2026

- **21/21 backend tests pass**: SigV4 thực với credential test giả, S3 HEAD
  dùng Stubber, repository dùng test double; kiểm tra key lấy từ repository,
  processed/raw policy, enrollment/ownership/identity, lỗi AWS và OpenAPI.
  Không coi các test này là xác nhận tích hợp AWS thật.
- **4/4 frontend API tests pass**: mock không gọi mạng, live gửi identity hiện
  có, truyền mã thiếu-video và lấy response mới không cache. Vite production
  build pass; có warning `use client` từ react-router.
- PostgreSQL local đọc được Lesson 8: title `Image vs Container`, course 2,
  instructor 1, course published, `raw_video_key=NULL`, `processed_video_key=NULL`.
  Không thay đổi dữ liệu/schema.
- HTTP thật: `GET /lessons/8` → **200**; `GET /lessons/8/video-url` →
  **404 VIDEO_NOT_AVAILABLE**; lesson không tồn tại → **404**; user không tồn
  tại → **401**. `/docs` → **200** HTML; schema endpoint đã kiểm tra qua OpenAPI.
- Boto3 credential provider không tìm thấy credentials trong phiên chạy.
  **Chưa kiểm thử object key hợp lệ đang nằm trong DB với S3 thật, GET/range
  từ S3, phát/tua MP4, hoặc refresh URL trên browser thật.**
- Điều khiển Chrome bị công cụ dừng với thông báo không xác định chắc chắn
  URL hiện tại để thực thi policy. Vì vậy **chưa thao tác Try it out trên UI
  Swagger, chưa xác minh trạng thái hiển thị trong browser**. Không dùng mock
  hoặc URL hardcode để báo rằng tích hợp AWS đã thành công.

Không triển khai confirm-upload, pipeline xử lý video/AI, login/JWT; không
thay đổi API Contract Draft, schema, database hoặc quyền bucket.
