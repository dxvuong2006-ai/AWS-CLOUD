# Hướng dẫn demo LearnCloud

## Chọn chế độ demo

| Chế độ | Dùng khi | Có thể khẳng định | Không được khẳng định |
|---|---|---|---|
| UI mock (`VITE_USE_MOCK=true`) | Demo bố cục/điều hướng nhanh | Giao diện và hành vi mock | Backend, PostgreSQL, Cognito, S3 hoặc AI thật hoạt động |
| Local integrated | FastAPI + SQLite/PostgreSQL test + local auth/fixture | Luồng local đã thực hiện và response API quan sát được | AWS production hoặc concurrency PostgreSQL nếu dùng SQLite |
| Non-production AWS | Có inventory/canary/credentials test được duyệt | Chỉ những bước có log/execution trong buổi demo | Production, resource khác môi trường hoặc tính năng chưa chạy |

Nói rõ chế độ ngay đầu buổi. Không chuyển từ mock sang real giữa demo mà không thông báo.

## Chuẩn bị

1. Làm theo [thiết lập local](../03-implementation/local-setup.md) hoặc runbook non-production được duyệt.
2. Ghi commit/artifact và kiểm tra working tree; không dùng code chưa biết phiên bản.
3. Chuẩn bị dữ liệu test cô lập: một Instructor sở hữu course `DRAFT`, Student test, Admin test, section/lesson/quiz phù hợp và không có dữ liệu cá nhân thật.
4. Nếu demo upload, dùng video ngắn không nhạy cảm và xác minh bucket/database test, budget, feature flags và cleanup owner. Không bật pipeline production chỉ để demo.
5. Mở sẵn health, ứng dụng và log đã làm sạch. Tắt password manager/autofill/notification có thể lộ dữ liệu.
6. Không lưu tài khoản/mật khẩu demo trong Markdown, slide, source hoặc ảnh. Nhập qua secret manager/kênh riêng và xóa khỏi clipboard/terminal history khi xong.

### Smoke test trước buổi demo

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health

Push-Location .\frontend
npm.cmd test
Pop-Location
```

Health mong đợi `{"status":"ok"}`. Test frontend pass chỉ xác nhận suite Node; vẫn cần mở đúng màn hình và thử dữ liệu demo.

## Kịch bản 12–15 phút

### 1. Mở đầu và kiến trúc - 1 phút

- Giới thiệu LearnCloud là LMS video-first có human-in-the-loop.
- Nêu ba vai trò và phân biệt M1–M8 với K1–K6.
- Nói rõ môi trường demo và trạng thái bằng chứng; không nói “production” nếu chỉ local/mock.

**Kết quả mong đợi:** người xem hiểu AI pipeline tạo bản nháp, còn Instructor chịu trách nhiệm duyệt.

### 2. Instructor - 4 phút

1. Đăng nhập bằng Instructor test qua kênh đã chuẩn bị.
2. Mở `/instructor/courses`, tạo hoặc chọn course `DRAFT`; xem section và lesson.
3. Mở trang upload `/instructor/courses/{courseId}/lessons/{lessonId}/upload`.
4. Nếu là local/mock, mô tả contract `upload-url` → PUT → `confirm-upload` và hiển thị trạng thái giả lập/fixture, không giả vờ đã PUT S3.
5. Nếu là non-production AWS đã duyệt, upload video test, theo dõi `processing-status` và dừng nếu pipeline lỗi; không mở presigned URL trong thanh địa chỉ hay log.
6. Mở review queue/draft, sửa một mục, kiểm tra validation và approve. Publish course chỉ khi dữ liệu test đủ điều kiện.
7. Mở Instructor dashboard/student report.

**Kết quả mong đợi:** course/lesson ownership được giữ; upload không đi qua backend; nội dung AI không tự đến Student; analytics chỉ thuộc course Instructor.

### 3. Student - 4 phút

1. Đăng nhập Student test và mở `/courses`.
2. Enroll course đã publish; mở `/my-courses` và một lesson được phép.
3. Trình bày video/transcript/summary/flashcard. Nếu video URL không có trong local, nói rõ giới hạn thay vì hardcode URL.
4. Làm checkpoint theo một trong ba fixture:
   - `>=80`: kết quả đạt và section kế mở;
   - `50–<80`: chưa đạt, section vẫn khóa, được retry ngay;
   - `<50`: retry bị chặn cho tới khi remediation hoàn tất.
5. Với nhánh `<50`, mở `/tutor/attempts/{attemptId}`, xem giải thích, ôn nội dung và nộp practice. Nói rõ Tutor đang dùng Bedrock hay fallback/fixture.

**Kết quả mong đợi:** backend quyết định score/unlock; đáp án đúng không lộ trước submit; remediation gắn đúng attempt/Student.

### 4. Admin - 2 phút

1. Đăng nhập Admin test và mở `/admin/users`.
2. Hiển thị tìm kiếm/danh sách, trạng thái tài khoản và thao tác đã được phép trên dữ liệu test.
3. Mở `/admin/monitoring` và giải thích đây là job/app view; CloudWatch Console là phạm vi operator riêng.

**Kết quả mong đợi:** Admin route tách khỏi Instructor/Student; vô hiệu hóa tài khoản được backend thực thi. Không thay role/status tài khoản dùng chung trong demo.


## Kịch bản ngắn 3–5 phút

1. `GET /health` và `/docs`: chứng minh backend/OpenAPI local.
2. Instructor: course → upload contract → review/publish bằng fixture.
3. Student: lesson → checkpoint `<50` → remediation → retry hoặc `>=80` → unlock.
4. Nêu rõ bằng chứng local so với phần AWS chưa xác minh.

Không cố nhồi cả ba Console AWS và mọi màn hình; ưu tiên một luồng có đầu vào/kết quả rõ.

## Xử lý sự cố

| Triệu chứng | Kiểm tra | Cách xử lý an toàn |
|---|---|---|
| Frontend không gọi được API | `VITE_API_URL`/`VITE_API_BASE_URL`, backend `127.0.0.1:8000`, CORS | Restart Vite sau đổi env; không tắt auth/CORS toàn cục để “chạy cho được” |
| `401` | Token/session/provider local vs Cognito | Đăng nhập lại đúng provider; không dùng mock token gọi API thật |
| `403` | Role, account status, ownership, enrollment, publish/unlock | Dùng fixture đúng; không sửa DB trực tiếp để bỏ gate |
| Upload dừng trước PUT | Type/size, upload ledger, overwrite guard | Dùng video test hợp lệ và lesson trống; không tái dùng key tùy ý |
| PUT xong nhưng UI chưa thành công | `confirm-upload`, HEAD metadata, feature flag | Không báo thành công trước confirm; xem safe error/request id |
| Pipeline đứng/`FAILED` | Flag, execution/run/job id, timeout và ledger | Dừng demo; không redrive submit mù hoặc bật production flag |
| Không có video | Key/policy/credential và raw playback policy | Dùng fixture hoặc ghi rõ chưa có S3; không hardcode public URL |
| Checkpoint chưa mở | Enrollment, lesson completion, quiz approval, section trước | Hoàn thành đúng prerequisite; không chỉnh client state để mở khóa |
| Retry dưới 50 bị chặn | Explanation/review/practice của đúng attempt | Hoàn tất remediation; không sửa `remediation_completed` trực tiếp |
| Tutor trả fallback | `TUTOR_USE_BEDROCK`, transcript, AWS config/quota | Gắn nhãn fallback; không tuyên bố Bedrock thành công |

## Kết thúc và dọn môi trường

- Dừng Uvicorn/Vite bằng `Ctrl+C`; dùng `docker compose stop` để giữ volume local.
- Không xóa bucket/RDS/CloudWatch/resource AWS trong buổi demo nếu không có change/cleanup plan được duyệt.
- Thu hồi session/token tạm, xóa video/object test theo quy trình owner sau khi xác nhận không còn execution phụ thuộc.
- Không commit `.env`, log, screenshot, dump, input PDF/spec, video test nhạy cảm hoặc credential.
- Ghi lại môi trường, thời điểm, kết quả/failed step và khoảng chưa xác minh mà không đưa secret/PII vào biên bản.
