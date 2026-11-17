# Kết quả hiện thực chức năng


## Tổng hợp M1–M8

| Module | Theo báo cáo 13/11/2026 | Có trong source hiện tại | Đã kiểm thử local ngày 17/11/2026 | AWS/RDS hiện tại |
|---|---|---|---|---|
| **M1 - Authentication** | Cognito/Amplify, ba vai trò, `/auth/me`, chặn 401/403 | Cognito JWT và local auth có điều kiện; route hồ sơ/đăng ký/xác minh/khôi phục; user `ACTIVE`/`INACTIVE`; UI theo role | Có trong backend offline/auth-P0 và frontend Node tests | **Chưa xác minh** pool/client/authorizer/user mapping đang chạy |
| **M2 - Course & Student** | Tạo/sửa/publish course, section, lesson, enrollment; ownership | Router/service/repository và UI Instructor/Student; course `DRAFT/PUBLISHED`; public catalog và protected resources | Có trong backend offline và frontend tests | **Chưa xác minh** dữ liệu/route deployment hiện tại |
| **M3 - Upload** | Presigned PUT thẳng S3, key gắn lesson, theo dõi trạng thái | Upload intent bất biến, loại/size/overwrite guard, `upload-url`, `confirm-upload`, S3 adapter | Logic/stub được bao phủ local; không gọi S3 thật trong lượt này | **Chưa xác minh** bucket, policy, CORS, object và PUT hiện tại |
| **M4 - Video & AI pipeline** | MediaConvert → Transcribe → Bedrock; transcript/summary/concepts/flashcard/quiz; retry/FAILED | K4/K5 handlers, ASL, EventBridge pattern, ledger, schema/prompt/processor; feature flags mặc định tắt | Unit/AI processor tests pass; không phải AWS E2E | **Chưa xác minh** state machine, model, execution và output production |
| **M5 - Review & Publishing** | Instructor sửa/approve; nội dung chưa duyệt không đến Student | Hai bề mặt API `review-draft*` và `ai-content`/`approve`, revision/locking, publish gate, UI review | Backend/frontend offline bao phủ lưu nháp, validation và approval/publish | **Chưa xác minh** flow với RDS/AWS hiện tại |
| **M6 - Learning & Checkpoint** | Video/transcript/summary/flashcard, progress, backend grading, 50/80, unlock | Protected content/video URL, watched ranges/session/idempotency, flashcard, quiz attempt/history, unlock service | Backend/frontend offline bao phủ score bands, access và replay | PostgreSQL concurrency/playback S3 thật **chưa xác minh** |
| **M7 - AI Tutor Remediation** | Phiên gắn attempt; giải thích, ví dụ, practice; dưới 50 phải hoàn tất remediation | Tutor và workflow remediation ba bước; context từ transcript/câu sai; Bedrock opt-in + fallback; server-owned eligibility | Service/context/frontend behavior được kiểm thử local | Bedrock/Guardrails/quota/runtime **chưa xác minh** |
| **M8 - Analytics & Monitoring** | Instructor analytics và CloudWatch logs/metrics | Analytics/dashboard/student report; admin monitoring jobs; logging/CloudWatch templates | Analytics/report logic có test local | Dashboard, log groups, alarms và Budgets **chưa xác minh** |

## M1 - Xác thực và quản lý người dùng

Báo cáo trình bày đăng nhập Cognito qua Amplify, giao diện riêng cho Instructor, Student, Admin và Admin quản lý tài khoản trên Cognito/CloudWatch. Source hiện tại rộng hơn: ngoài Cognito còn có local auth chỉ được phép trong `development`/`test`, luồng OTP/khôi phục, cập nhật hồ sơ, đổi mật khẩu, admin tạo/sửa/vô hiệu hóa user và reconciliation Cognito–RDS theo `sub`.

Ranh giới bảo mật nằm ở backend: token hợp lệ vẫn có thể nhận `403` nếu sai role/ownership; user `INACTIVE` bị từ chối. Local auth không được mô tả như lựa chọn production.

## M2 - Khóa học và học viên

Source xác nhận course mới do Instructor tạo ở `DRAFT`; section và lesson có `position`; enrollment lấy Student từ token, không nhận student id tùy ý. Các route Instructor, catalog, chi tiết course, danh sách course của Student và báo cáo học viên hiện diện trong OpenAPI. Enrollment chỉ là ghi danh, không có payment.

Điểm cần lưu ý: một số hành vi public/protected và publish chi tiết đã phát triển sau bảng API trong PDF; exact contract phải lấy từ [OpenAPI hiện tại](../02-architecture/api-contract.md), không từ path rút gọn trong báo cáo.

## M3 - Upload video

Báo cáo mô tả `POST /lessons/{id}/upload-url` và browser PUT trực tiếp lên S3. Source hiện tại bổ sung ledger `video_uploads`, upload id 32 ký tự hex, key bất biến, `If-None-Match: *`, giới hạn 500 MiB và bước `POST /lessons/{id}/confirm-upload` bắt buộc ở frontend. Confirm chỉ HEAD/đối chiếu metadata và gắn raw key; S3 EventBridge vẫn là initial dispatcher duy nhất khi pipeline được bật.

Đây là khác biệt có chủ ý so với mô tả PDF, nhằm chống overwrite, upload mồ côi và báo thành công trước khi backend xác nhận object.

## M4 - Xử lý video và học liệu AI

Repository có pipeline hai worker:

- K4 claim upload, tạo/poll MediaConvert, xác minh output, quản lý ledger và failure.
- K5 bắt đầu/poll Transcribe, gọi Bedrock, kiểm tra đầu ra và trả proof để K4 finalize.

ASL có timeout/retry/Catch, bounded polling, duplicate ignore và không tự retry submit MediaConvert. `ai_pipeline/` chứa JSON schema, prompt, processor và fixture. Source tồn tại không chứng minh MediaConvert/Transcribe/Bedrock đang chạy; cả `VIDEO_AI_ENABLED` và `AI_WORKER_ENABLED` mặc định `false`.

## M5 - Review và publish

Source hỗ trợ lấy/sửa/duyệt nội dung với ownership, revision và transaction/lock. Quiz/flashcard trước duyệt không được coi là public. Báo cáo dùng ba endpoint `GET/PATCH /lessons/{id}/ai-content`, `POST /lessons/{id}/approve`; OpenAPI hiện tại giữ các endpoint này và thêm `review-draft*` cho workflow màn hình.

Lịch sử migration từng thêm rồi loại trạng thái `APPROVED`; enum source hiện tại dùng `REVIEW_REQUIRED` và `PUBLISHED`. Vì vậy không được áp migration theo tên file mà chưa đối soát database.

## M6 - Học tập, flashcard và checkpoint

Các quy tắc cốt lõi trong PDF vẫn có trong source: backend giữ đáp án/chấm điểm, `>=80` đạt, `50–<80` cho retry ngay, `<50` bắt buộc remediation; unlock suy từ attempt đạt. Source còn bổ sung request id/hash cho submit idempotent, viewing session/sequence/watched ranges và nhiều endpoint history/overview.

Khác biệt quan trọng: `COMPLETION_THRESHOLD=0.1` trong source là ngưỡng quick-test hiện tại, không phải tiêu chuẩn học tập 95%/100% đã được chốt. Trước production cần đưa thành cấu hình/quyết định sản phẩm và kiểm thử lại migration/trigger.

## M7 - AI Tutor

Source kiểm tra attempt thuộc Student, chỉ lấy lesson đã publish và transcript/câu sai liên quan. Khi bật `TUTOR_USE_BEDROCK`, adapter gọi Bedrock; nếu không, builder/fallback vẫn có thể tạo nội dung có cấu trúc để phát triển local. Do đó output Tutor trong test local không chứng minh Bedrock đã được gọi.

Luồng remediation ba bước lưu explanation/review/practice state và chỉ tạo eligibility server-side khi practice đạt. Báo cáo nói Tutor có Guardrails và giới hạn lượt gọi hằng ngày; cấu hình Guardrails/quota tương ứng chưa được xác minh trong runtime/source hiện tại, nên không được ghi là đã hoàn tất production.

## M8 - Analytics và giám sát

Source có Instructor dashboard, course analytics, quiz analytics, student report và admin monitoring jobs. Learning analytics lấy dữ liệu ứng dụng và kiểm tra ownership; cloud monitoring thuộc phạm vi vận hành AWS. Hai nhóm này không nên trộn quyền truy cập.

## Kết luận nghiệm thu chức năng

M1–M8 đều có thành phần tương ứng trong source và các luồng offline quan trọng đã được kiểm thử local. Không có đủ bằng chứng trong lượt này để nâng bất kỳ module nào lên trạng thái “đã xác minh AWS production hiện tại”; đặc biệt K4/K5, S3 playback thật, PostgreSQL concurrency/migration và Cognito/RDS reconciliation vẫn cần test môi trường cô lập hoặc inventory/log có ngày.
