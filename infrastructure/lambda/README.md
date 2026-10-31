# LearnCloud — Smoke test AWS Lambda → Amazon RDS

Đây **chỉ là một probe tích hợp chỉ đọc**, không phải Lambda xử lý video dành cho môi trường production. Probe kết nối trực tiếp đến **endpoint RDS private qua VPC**, xác thực với PostgreSQL, thực thi truy vấn SQL chỉ đọc và kiểm tra TLS. Lambda không cần port-forwarding qua EC2/SSM.

## Build trên Windows (không cần phần mềm bổ sung)

Giải nén các tệp này, mở PowerShell trong thư mục đã giải nén và chạy:

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

Script sử dụng Python LearnCloud hiện có của bạn (hoặc Python trên Windows), tải xuống **pg8000 (Python thuần)** và gói chứng chỉ RDS Singapore chính thức, sau đó tạo `learncloud-rds-probe.zip` trong thư mục đó. Script không cài đặt ứng dụng hệ thống.

## Cài đặt trên AWS Console

- Region: `ap-southeast-1`
- Tên function: `learncloud-rds-probe`; Runtime: Python 3.12; Kiến trúc: x86_64; Handler: `lambda_function.lambda_handler`; Timeout: 20 giây; Memory: 256 MB.
- IAM role thực thi: `learncloud-rds-probe-role` với `AWSLambdaBasicExecutionRole` và `AWSLambdaVPCAccessExecutionRole`.
- VPC: `vpc-0255e992edb53b226`, hai subnet trong VPC đó, security group `learncloud-lambda-sg` (hãy tạo security group này).
- `learncloud-lambda-sg` cho phép outbound TCP 5432 -> `learncloud-rds-sg` (`sg-047b6fe18a2919fa9`); không cần inbound.
- Security group RDS `sg-047b6fe18a2919fa9` cho phép inbound PostgreSQL TCP 5432 **từ ID của Lambda security group**. Giữ nguyên rule hiện có cho cầu nối EC2/SSM.
- Code → Upload from → .zip file → `learncloud-rds-probe.zip`.
- Configuration → Environment variables:
  - `DB_HOST=learncloud-db.cjswky2qyz14.ap-southeast-1.rds.amazonaws.com`
  - `DB_PORT=5432`
  - `DB_NAME=learncloud`
  - `DB_USER=learncloud_lambda_probe`
  - `DB_PASSWORD=(mật khẩu của DB role probe; không dán vào chat hoặc repo)`

Tạo một PostgreSQL role riêng với quyền hạn chế bằng công cụ truy vấn SQL của pgAdmin (thay mật khẩu bằng một mật khẩu mạnh được tạo ngẫu nhiên):

```sql
CREATE ROLE learncloud_lambda_probe LOGIN PASSWORD 'REPLACE_WITH_STRONG_PASSWORD';
GRANT CONNECT ON DATABASE learncloud TO learncloud_lambda_probe;
GRANT USAGE ON SCHEMA public TO learncloud_lambda_probe;
GRANT SELECT ON TABLE public.courses, public.lessons TO learncloud_lambda_probe;
```

**Quan trọng:** **Không** commit câu lệnh SQL tạo role có chứa mật khẩu thật vào Git; các câu lệnh SQL cũng có thể vẫn còn trong Query History. Sử dụng một user probe chỉ đọc riêng sẽ an toàn hơn việc phân phối mật khẩu admin RDS. Nếu role này đã tồn tại, không chạy lại `CREATE ROLE`; hãy đặt lại mật khẩu nếu cần.

## Kiểm thử

Lambda → Test → create event `{}` → Test. Kết quả mong đợi:

```json
{
  "ok": true,
  "database": "learncloud",
  "user": "learncloud_lambda_probe",
  "courses": 4,
  "lessons": 12,
  "tls_enabled": true
}
```

Phản hồi cũng bao gồm `duration_ms` (giá trị không được định trước). Nếu `ok=false`, hãy kiểm tra log CloudWatch, loại lỗi, cài đặt mạng, quyền IAM và thông tin xác thực DB. Không bao giờ chia sẻ secret hoặc connection string thật.

## Bảo mật và triển khai tiếp theo

- Lambda nên sử dụng **RDS hostname thật:5432**, **không phải** `127.0.0.1:15437`.
- Bài kiểm thử chỉ sử dụng biến môi trường Lambda được mã hóa cho một **smoke test phát triển tạm thời**. AWS khuyến nghị sử dụng **Secrets Manager** để lưu thông tin xác thực cơ sở dữ liệu. Nếu function không có NAT, Lambda gắn với VPC cần một **Secrets Manager interface VPC endpoint** (đây là dịch vụ tính phí) để truy cập Secrets Manager; hãy cấp quyền đọc IAM theo nguyên tắc đặc quyền tối thiểu. Hãy sử dụng cách này cho Lambda pipeline production thay vì để thông tin xác thực dạng plaintext mà người đọc cấu hình Lambda có thể truy cập.
- Lambda gắn với VPC thường không có quyền truy cập Internet công khai nếu không có NAT/endpoint. Probe **không thực hiện bất kỳ HTTP request bên ngoài nào**. Lambda xử lý video có thể cần các endpoint S3/Bedrock riêng hoặc NAT.
- Xóa thông tin xác thực hoặc xóa probe tạm thời sau khi xác nhận kết nối; sử dụng một DB role riêng cho ứng dụng trong pipeline thực tế.
