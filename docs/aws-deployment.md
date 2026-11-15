# Triển khai và vận hành trên AWS

## Trạng thái đã xác minh

Repository có code đóng gói Lambda/Mangum, ví dụ triển khai, mẫu IAM và cấu hình API Gateway, S3, EventBridge, Step Functions. Các artifact này chỉ thể hiện tích hợp dự kiến. Lần cập nhật tài liệu này không gọi AWS; tài nguyên hiện tại trong account, frontend URL, API route, Lambda version/alias, Cognito, RDS schema và trạng thái pipeline đều **chưa được xác minh**. Runbook cũ có ghi nhận deployment/test ở thời điểm trước; cần đối chiếu inventory mới trước khi thao tác.

## Các cổng trước khi triển khai

1. Xác định account, Region, môi trường và operator đã được duyệt. Xác nhận danh tính AWS qua phương thức truy cập của nhóm; không chép credential/token vào repository.
2. Ghi commit SHA chính xác và review working tree. Tạo artifact backend/frontend từ commit đó; loại `.env`, `.aws`, cache local và test-only handler khỏi package production. Script trong repository chỉ hỗ trợ chuẩn bị artifact, không phải một deploy pipeline hoàn chỉnh: `package_lambda.py` tạo code ZIP, `infrastructure/deployment/render-k4-k5-production.ps1` render cấu hình pipeline, còn `infrastructure/lambda/build.ps1` tạo package RDS probe. Xác minh việc đóng gói dependency và handler/runtime tương thích với Lambda đích; không mặc định ZIP tổng quát tự nó deploy được.
3. Đối chiếu source dự kiến với API Gateway authorizer/route, Lambda runtime/handler/config, Cognito pool/client, RDS endpoint/schema và S3 bucket policy đang chạy. Template source không thay thế inventory thực tế.
4. Review IAM theo least privilege, kết nối VPC, TLS/database, CORS origin, S3 public-access block, mã hóa và logging. Giữ `VIDEO_PIPELINE_ENABLED`, `VIDEO_AI_ENABLED`, `AI_WORKER_ENABLED` tắt cho tới khi các gate non-production đạt.
5. Với thay đổi schema, lập kế hoạch migration được review riêng: xác minh database và registry, tạo snapshot/backup đã duyệt, chạy preflight chỉ đọc phù hợp, chỉ apply migration đã review rồi chạy postflight và integration check. Lịch sử migration có nhiều file trùng version `0004`.
6. Deploy backend/frontend artifact tới đích đã duyệt; chỉ cập nhật API/Cognito/frontend setting đã review. Sau đó kiểm tra health, auth, log và business flow bị ảnh hưởng. Ghi hash artifact và version/alias mới, không ghi secret.
7. Chỉ bật video/AI bất đồng bộ sau khi E2E non-production xác minh duplicate/retry, output state, logging và chi phí. Source mặc định tắt các tính năng này.

## Rollback và phục hồi

- Giữ sẵn backend version/alias tốt trước đó và frontend artifact cũ theo quy trình deploy của nhóm. Khi ứng dụng lỗi, chuyển traffic về version/artifact đó rồi xác minh health/auth trước khi tiếp tục.
- Thay đổi database cần quyết định phục hồi riêng cho migration. Ưu tiên forward-fix đã review hoặc restore từ snapshot trước thay đổi; không drop bảng, chạy lại migration không rõ trạng thái hoặc mặc định down script an toàn.
- Khi retry video pipeline, đối soát upload/ledger, MediaConvert job và object trước khi gửi job mới. Tham khảo [runbook video pipeline](aws/video-pipeline-console-setup.md) và [runbook E2E](operations/k4-k5-e2e-test-runbook.md); không redrive mù qua ranh giới không idempotent.
- Giữ log và request/execution identifier. Không ghi access token, database URL/password, raw AWS exception, transcript hoặc presigned URL vào log/ticket.

Repository không có một script duy nhất để deploy toàn bộ frontend/backend/database/pipeline và rollback atomically. Thực hiện theo change process được duyệt cho đúng account; giữ artifact/version trước đó cho từng thành phần triển khai độc lập.

## Lưu ý bảo mật

- Dùng federated identity riêng cho từng người, MFA và role có phạm vi hẹp; không dùng chung root access key.
- Giữ RDS private, chỉ cho phép inbound từ security group cần thiết. S3 bucket phải private và object prefix được giới hạn quyền.
- Lưu database secret qua cơ chế inject secret đã duyệt. Backend hiện đọc `DATABASE_URL`, không tự lấy giá trị từ Secrets Manager.
- Coi presigned URL và auth token là bearer credential tạm thời. Không đưa chúng vào screenshot, commit hoặc chat.
- Cấu hình CloudWatch retention/alarm và AWS Budget trước khi chạy MediaConvert, Transcribe hoặc Bedrock có chi phí.

## Runbook liên quan

- [Ghi chú API Gateway và Lambda](aws/api-gateway-lambda.md)
- [Đối soát danh tính Cognito/RDS](aws/cognito-rds-reconciliation.md)
- [Ghi chú phát video từ S3](aws/s3-video-playback.md)
- [Chuẩn bị rollout K4/K5](aws/k4-k5-production-rollout.md)
- [Script đóng gói Lambda](../package_lambda.py)
- [Script render cấu hình K4/K5](../infrastructure/deployment/render-k4-k5-production.ps1)

Các runbook chuyên biệt có hướng dẫn triển khai và ghi nhận lịch sử. Xác minh tên tài nguyên, quyền và schema hiện hành trước khi sử dụng; tài liệu này không xác nhận deployment production nào đang hoạt động.
