# Tài liệu LearnCloud

## 01 - Tổng quan

Dành cho người đọc muốn hiểu bài toán, phạm vi MVP, vai trò và luồng nghiệp vụ.

- [Tổng quan dự án](01-overview/project-overview.md)
- [Luồng người dùng](01-overview/user-workflows.md)

## 02 - Kiến trúc

Dành cho nhà phát triển, người review bảo mật và người vận hành cần phân biệt M1–M8 với K1–K6.

- [Kiến trúc chức năng M1–M8](02-architecture/functional-architecture.md)
- [Kiến trúc AWS K1–K6](02-architecture/aws-architecture.md)
- [Luồng dữ liệu](02-architecture/data-flows.md)
- [Bảo mật và rủi ro](02-architecture/security-and-risks.md)
- [Hợp đồng API](02-architecture/api-contract.md)
- [Thiết kế database](02-architecture/database-design.md)

## 03 - Hiện thực và triển khai

Dành cho thành viên cần chạy local, chuẩn bị thay đổi AWS hoặc đối chiếu kết quả chức năng.

- [Thiết lập local](03-implementation/local-setup.md)
- [Triển khai AWS](03-implementation/aws-deployment.md)
- [Kết quả chức năng](03-implementation/feature-results.md)

## 04 - Đánh giá

Dành cho người nghiệm thu cần biết test nào đã chạy, số liệu nào chỉ đến từ báo cáo và các giới hạn còn lại.

- [Kiểm thử](04-evaluation/testing.md)
- [AI và hiệu năng](04-evaluation/ai-and-performance.md)
- [Giới hạn](04-evaluation/limitations.md)

## 05 - Demo

- [Hướng dẫn demo theo vai trò](05-demo/demo-guide.md)

## Runbook vận hành

Runbook dưới đây chứa quy trình riêng chưa bị thay thế bởi 17 tài liệu chính. Nội dung đã được đối chiếu với source, nhưng vẫn phải xác minh inventory và target trước mọi thao tác ghi:

- [Đối soát danh tính Cognito/RDS](../infrastructure/cognito/cognito-rds-reconciliation.md)
- [Quy ước migration](../database/migrations/README.md)

## Tài liệu lưu trữ

`docs/archive/` chứa các snapshot triển khai, migration và kiểm thử theo thời điểm. Mỗi file có cảnh báo **TÀI LIỆU LỊCH SỬ - KHÔNG XÁC MINH HIỆN TẠI**; chúng không phải hướng dẫn mặc định và không được dùng làm inventory AWS/RDS.

### AWS và pipeline

- [Bàn giao API Gateway/Lambda](archive/aws/api-gateway-lambda.md)
- [Rollout production K4/K5](archive/aws/k4-k5-production-rollout.md)
- [Playback MP4 từ S3](archive/aws/s3-video-playback.md)
- [Thiết lập pipeline qua AWS Console](archive/aws/video-pipeline-console-setup.md)

### Database và migration

- [Migration phê duyệt Lesson](archive/database/lesson-approval-migration.md)
- [Migration ledger video 0005](archive/database/video-pipeline-migration-0005.md)

### Kiểm thử và giai đoạn triển khai

- [Regression backend lịch sử](archive/operations/backend-regression-report.md)
- [K4/K5 E2E cô lập](archive/operations/k4-k5-e2e-test-runbook.md)
- [Video processing giai đoạn 1](archive/operations/video-processing-phase1.md)

Không đưa credential, token, mật khẩu, OTP, private key, presigned URL hay tài khoản demo vào tài liệu/issue. Các file đầu vào tạm thời của bộ tài liệu không thuộc phạm vi Git.
