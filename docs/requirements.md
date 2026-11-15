# Chức năng và quy tắc nghiệp vụ hiện tại

Tài liệu này mô tả khả năng hiện diện trong source hiện tại. Các trường hợp có test được ghi nhận riêng; việc tồn tại source hoặc test offline không xác nhận tích hợp production/AWS.

## Vai trò và xác thực

- Backend có vai trò `STUDENT`, `INSTRUCTOR`, `ADMIN`; user có trạng thái `ACTIVE`/`INACTIVE`. Các dependency backend xác minh bearer token, đồng bộ/tra user và chặn tài khoản bị vô hiệu hóa.
- Source có luồng Cognito và local auth có điều kiện (`LOCAL_AUTH_ENABLED`); local auth chỉ dành cho development/test. Frontend có Amplify Auth và API client bearer token.
- Route/endpoint công khai không đồng nghĩa với endpoint không có giới hạn nghiệp vụ. Backend chịu trách nhiệm kiểm tra role, ownership và trạng thái tài khoản.

## Course, section và lesson

- Instructor/admin tạo và quản lý course; course có `DRAFT` hoặc `PUBLISHED`. Course chứa sections và lessons có vị trí thứ tự.
- Instructor có thể tạo/sửa nội dung; thao tác review/approve và publish có endpoint riêng. Publish phụ thuộc trạng thái và điều kiện trong backend/database.
- Course public listing/detail được hỗ trợ; nội dung lesson được bảo vệ bằng xác thực và các điều kiện truy cập tương ứng.

## Upload và xử lý video

- Backend có tạo presigned upload URL, xác nhận upload, lấy trạng thái xử lý, retry và video playback URL. S3 adapter và video-processing adapter có implementation local/AWS.
- Source có EventBridge, Step Functions, MediaConvert, Transcribe và Bedrock worker templates cùng feature flags mặc định tắt.
- `202` hoặc trạng thái `PROCESSING` chỉ xác nhận request/job đã được nhận theo contract; không khẳng định có output media hoặc AI hoàn chỉnh. E2E AWS production chưa được xác minh trong lần audit này.

## Nội dung AI, quiz và học tập

- Source có transcript, summary/key concepts, quiz, flashcard, review draft và approval. Câu trả lời đúng được giữ phía server trước khi nộp quiz.
- Quiz được lưu theo section; backend chấm attempt, lưu lịch sử và điều khiển retry/unlock. Không coi dữ liệu mock/frontend là quyền truy cập có thẩm quyền.
- Progress lưu vị trí xem, watched ranges, viewing session và trạng thái hoàn tất; có trigger/migration bổ sung integrity cho duration/completion.
- Tutor có remediation/session/message/practice operations. Việc đầy đủ AI remediation phụ thuộc services, cấu hình và dữ liệu điều kiện; không mặc định mọi nhánh đã được E2E kiểm chứng.

## Analytics và quản trị

- Source có instructor dashboard/course/student reports, quiz analytics, admin user lifecycle/status và monitoring jobs.
- Quyền quản trị và trạng thái tài khoản do backend kiểm soát; giao diện frontend không phải ranh giới bảo mật.

## Trạng thái bằng chứng

| Mức | Hiện trạng |
|---|---|
| Có trong source | Backend FastAPI, React/Vite, adapter AI/video/storage, pipeline AWS mẫu và database schema/migrations hiện diện trong repository. |
| Có test | Có unit/integration tests ở backend, frontend và AI pipeline. Báo cáo [backend regression](operations/backend-regression-report.md) ghi 463 pass, 0 fail, 69 PostgreSQL-gated skip ở lượt đã lưu; skip chưa được xác minh là pass trên PostgreSQL. |
| Đã xác nhận trên AWS | Chưa xác minh trong lượt audit này. Tài liệu cũ có ghi nhận một số triển khai/test lịch sử; không dùng các ghi nhận ấy làm trạng thái hiện hành. |
| Chưa xác minh | Tài nguyên production hiện tại, phiên bản Lambda/alias, API Gateway routing/authorizer, Cognito/RDS/S3 policies, K4/K5 E2E production, rollback gần nhất và trạng thái migrations trên RDS. |

## Ngoài phạm vi đã chứng minh

Không suy ra thanh toán, livestream, DRM, ứng dụng di động, hay khả năng AI/video production-ready từ tài liệu thiết kế hoặc tệp cấu hình mẫu. Đây không phải cam kết về roadmap.
