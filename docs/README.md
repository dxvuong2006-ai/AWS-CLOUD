# Tài liệu LearnCloud

Tài liệu này là điểm vào cho nhóm bảo trì và bàn giao LearnCloud. Tài liệu mô tả source và cấu hình trong repository; source không chứng minh một tài nguyên AWS đang chạy. Báo cáo kiểm thử ghi rõ phạm vi, kết quả, skip và giới hạn xác minh. Trạng thái AWS production hiện chưa được kiểm tra trong đợt dọn tài liệu này.

## Đọc theo nhu cầu

| Tài liệu | Nội dung |
|---|---|
| [Yêu cầu và quy tắc nghiệp vụ](requirements.md) | Hành vi có trong backend/frontend và các giới hạn đã biết. |
| [Kiến trúc](architecture.md) | Các thành phần source, luồng local/AWS dự kiến và trạng thái xác minh. |
| [API contract](api-contract.md) | Toàn bộ operation hiện có trong FastAPI OpenAPI. |
| [Database](database.md) | Bảng, quan hệ, nguồn schema và lịch sử migrations. |
| [Thiết lập local](local-setup.md) | Cài dependencies, khởi động dịch vụ local và cấu hình an toàn. |
| [Triển khai AWS](aws-deployment.md) | Quy trình kiểm tra, triển khai, rollback và ranh giới bằng chứng. |
| [Kịch bản demo](demo-script.md) | Demo local giới hạn ở những bước có thể xác minh an toàn. |

## Tài liệu chuyên sâu

- `aws/`: API Gateway/Lambda, Cognito/RDS, S3 playback và pipeline video. Nội dung triển khai cũ được giữ làm runbook tham khảo; phải kiểm tra cấu hình hiện hành trước khi dùng.
- `database/`: hướng dẫn review migration chuyên biệt; không phải migrations đã áp dụng.
- `operations/`: runbook E2E và báo cáo kiểm thử có phạm vi cụ thể.
- [Quy ước migrations](../database/migrations/README.md): lịch sử version, nhánh lịch sử và các guard.
- [Infrastructure source](../infrastructure/): cấu hình mẫu và scripts. Tệp cấu hình không xác minh trạng thái tài khoản AWS.

## Cách diễn giải trạng thái

- **Có trong source**: route, component, adapter, schema hoặc hạ tầng đã được định nghĩa trong repository.
- **Được kiểm thử**: có báo cáo hoặc test tương ứng; cần đọc phạm vi và loại môi trường.
- **Đã xác nhận trên AWS**: chỉ ghi khi có biên bản/inventory triển khai có thể đối chiếu. Tài liệu hiện có chứa các ghi nhận lịch sử, nhưng lần dọn này không gọi AWS và không xác nhận chúng còn đúng.
- **Chưa xác minh**: không có bằng chứng hiện hành đủ để kết luận.

Không ghi credentials, access tokens, password thật, private key hoặc presigned URL còn hiệu lực trong docs. Không chạy migration hay deploy chỉ bằng cách làm theo các ví dụ nếu chưa xác nhận môi trường đích.
