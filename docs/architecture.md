# Kiến trúc LearnCloud

## Tổng quan hệ thống

```text
Browser ── React + Vite (frontend/) ── HTTPS/JSON ── FastAPI (backend/)
                                                        ├── PostgreSQL (database/)
                                                        ├── Storage adapter: local / S3
                                                        ├── Auth: Cognito JWT / local auth tùy chọn
                                                        ├── AI adapter: mock / Bedrock
                                                        └── Video/transcription adapters

Cấu hình pipeline AWS (có trong source, chưa xác minh triển khai):
S3 event → EventBridge → Step Functions → Lambda workers
                                  ├── MediaConvert
                                  ├── Transcribe
                                  └── Bedrock → PostgreSQL/S3
Frontend static build → S3/CloudFront (đích triển khai)
API Gateway → Lambda + Mangum → FastAPI → RDS PostgreSQL (đích triển khai)
```

## Các thành phần trong repository

| Thành phần | Vai trò và bằng chứng |
|---|---|
| `frontend/` | Ứng dụng React/Vite, xác thực Amplify, API client và kiểm thử trình duyệt. Việc hiển thị route trên frontend không phải cơ chế phân quyền. |
| `backend/app/api/` | Router FastAPI, kiểm tra request/response; các router đã đăng ký tạo ra OpenAPI contract. |
| `backend/app/services/` | Quy tắc ứng dụng cho xác thực, khóa học, upload/video, tiến độ, quiz, review, Tutor và analytics. |
| `backend/app/repositories/`, `models/` | Truy vấn lưu trữ và các entity SQLAlchemy. |
| `backend/app/adapters/` | Các implementation local/AWS cho lưu trữ, xử lý video, phiên âm và AI. |
| `ai_pipeline/` | Chuẩn hóa transcript, tạo summary/quiz/key concepts và ngữ cảnh Tutor, kèm JSON schema và test. |
| `database/` | Schema khởi tạo PostgreSQL, migrations theo thứ tự/lịch sử, các kiểm tra và fixture test. |
| `infrastructure/` | Ví dụ đóng gói Lambda, mẫu IAM, EventBridge, ASL và script triển khai. Đây là artifact trong source, không chứng minh tài nguyên đã được deploy. |

## Luồng dữ liệu và request chính

1. Trình duyệt xác thực rồi gửi bearer access token tới FastAPI. Backend xác minh danh tính và kiểm tra tài khoản, role, ownership, enrollment cùng quyền truy cập nội dung.
2. Instructor tạo cấu trúc course và nội dung lesson. Video được tải lên bằng presigned S3 URL; route xác nhận upload và trạng thái xử lý theo dõi vòng đời upload.
3. Khi được cấu hình, S3/EventBridge/Step Functions điều phối các worker video và AI. Nội dung lesson phải qua instructor review/approval trước khi publish.
4. Student đăng ký, xem nội dung đã publish mà mình được phép truy cập, lưu tiến độ, nộp quiz và sử dụng các luồng review/Tutor được cấp quyền. Backend/database chịu trách nhiệm về điểm, completion và unlock.

## Chế độ local và AWS

Môi trường local chạy Vite và Uvicorn, có thể dùng PostgreSQL trong Compose khi cần database. Local auth, hàng đợi video local, mock AI và SQLite là các chế độ riêng; cần bật/cấu hình rõ ràng khi sử dụng.

Kiến trúc AWS được biểu diễn trong code/configuration cho Cognito, API Gateway, Lambda, RDS, S3, CloudFront, IAM, EventBridge và Step Functions. Feature flag cho video/AI mặc định tắt. Đợt cập nhật tài liệu này không kiểm tra inventory hay runtime trên AWS; topology đang deploy và các chức năng khả dụng **chưa được xác minh**. Xem [hướng dẫn AWS](aws-deployment.md).

## Ranh giới bảo mật

- Bundle trình duyệt có thể chứa Cognito/API identifier công khai, nhưng tuyệt đối không chứa private key, thông tin database hay AWS credentials.
- S3 phải giữ private; presigned URL là bearer capability có thời hạn ngắn, không được ghi log hoặc chia sẻ.
- Backend dependency/service và database mới là nơi thực thi authorization; không dựa vào kiểm tra trên giao diện.
- Runtime database role và AWS role cần theo least privilege đã review. Mẫu policy/config có sẵn vẫn phải được kiểm tra riêng cho từng môi trường.
