# LearnCloud — Hướng dẫn kết nối FastAPI với Amazon RDS PostgreSQL

> **Đối tượng:** Thành viên nhóm LearnCloud chạy backend trên máy Windows và cần sử dụng cơ sở dữ liệu AWS RDS chung.
>
> **Phạm vi:** Kết nối **FastAPI chạy local → SSM Port Forwarding → EC2 → RDS PostgreSQL private**. Đây là cách kết nối phục vụ phát triển/kiểm thử; **không** phải kiến trúc triển khai backend production.
>
> **Trạng thái kiểm chứng (31/10/2026):** Kết nối FastAPI tới RDS thành công; `GET /courses` trả về `200 OK`.

## 1. Kiến trúc kết nối

```text
Máy Windows của thành viên
  |
  | FastAPI / SQLAlchemy / psycopg2
  | host=127.0.0.1, port=15437
  v
AWS Systems Manager (SSM) Port Forwarding
  |
  v
EC2: learncloud-rds-bridge (trong VPC)
  |
  | PostgreSQL TCP 5432 (nội bộ VPC)
  v
Amazon RDS PostgreSQL: learncloud-db (private)
```

- RDS có **Public access = No**; không kết nối trực tiếp từ Internet.
- EC2 làm máy trung chuyển (bridge/bastion qua SSM), **không cần mở SSH port 22**.
- Cửa sổ lệnh chạy SSM phải duy trì mở trong suốt thời gian backend truy cập RDS.
- `127.0.0.1:15437` là cổng **trên máy Windows**, không phải cổng RDS công khai.

## 2. Thông số môi trường LearnCloud

| Thành phần | Giá trị |
|---|---|
| AWS Region | `ap-southeast-1` (Singapore) |
| RDS DB instance identifier | `learncloud-db` |
| RDS endpoint | `learncloud-db.cjswky2qyz14.ap-southeast-1.rds.amazonaws.com` |
| RDS port | `5432` |
| Database name | `learncloud` |
| Database user đang dùng để kiểm thử | `learncloud_admin` |
| EC2 bridge | `learncloud-rds-bridge` |
| EC2 instance ID | `i-0c9692401b32c5922` |
| Local forwarded port | `15437` |
| AWS CLI profile ví dụ | `learncloud` (mỗi máy có thể đặt tên khác) |
| Repo ví dụ | `D:\projects\main projects\AWS-CLOUD` |

**Không đưa mật khẩu database, AWS access key, `.env`, hay JWT secret vào Git/repo/chat.** Các giá trị định danh tài nguyên trên chỉ phục vụ cấu hình kết nối; quyền truy cập thực tế vẫn do IAM và RDS kiểm soát.

## 3. Điều kiện trước khi kết nối

Mỗi thành viên cần:

1. Có bản sao repository LearnCloud và Python virtual environment/requirements của backend.
2. Có **AWS CLI v2** và **AWS Session Manager Plugin** trên Windows.
3. Có AWS credentials/profile **riêng**, được cấp quyền bắt đầu SSM session tới đúng EC2 bridge và tài liệu `AWS-StartPortForwardingSessionToRemoteHost`.
4. Được người phụ trách cấp **database username/password hợp lệ**. Mật khẩu này là mật khẩu **PostgreSQL trên RDS**, *không phải* mật khẩu mở ứng dụng pgAdmin.
5. EC2 bridge đang chạy và online trong Systems Manager; security group của RDS cho phép TCP `5432` từ security group của EC2 bridge.

**Khuyến nghị bảo mật:** Không phát tán tài khoản `learncloud_admin` cho cả nhóm nếu có thể. Nên tạo PostgreSQL user riêng cho ứng dụng hoặc người phát triển, chỉ cấp quyền cần thiết; không chia sẻ cùng một AWS access key.

### Kiểm tra công cụ (PowerShell)

```powershell
aws --version
session-manager-plugin --version
aws sts get-caller-identity --profile learncloud
```

> Nếu profile trên máy có tên khác, thay `learncloud` trong tất cả lệnh dưới đây.

## 4. Mở SSM Tunnel từ Windows đến RDS

**Bước 1:** Mở một cửa sổ PowerShell riêng và chạy:

```powershell
$ec2Id = "i-0c9692401b32c5922"
$rdsHost = "learncloud-db.cjswky2qyz14.ap-southeast-1.rds.amazonaws.com"

aws ssm start-session `
  --target $ec2Id `
  --region ap-southeast-1 `
  --profile learncloud `
  --document-name AWS-StartPortForwardingSessionToRemoteHost `
  --parameters "host=$rdsHost,portNumber=5432,localPortNumber=15437"
```

Khi thành công, terminal sẽ hiển thị thông báo tương tự:

```text
Starting session with SessionId: ...
Port 15437 opened for sessionId ...
Waiting for connections...
```

**Không đóng cửa sổ này** khi chạy FastAPI hoặc pgAdmin. Khi có truy cập, có thể thấy `Connection accepted`.

**Bước 2:** Mở **cửa sổ PowerShell thứ hai** để kiểm tra cổng local:

```powershell
Test-NetConnection 127.0.0.1 -Port 15437
```

Kết quả mong đợi:

```text
TcpTestSucceeded : True
```

> `True` chỉ xác nhận đường truyền TCP tới tunnel; chưa xác nhận mật khẩu PostgreSQL.

## 5. Cấu hình `.env` cho FastAPI

Mở file `.env` mà backend LearnCloud thực sự đọc (trong lần triển khai này là file ở thư mục gốc repository):

```text
D:\projects\main projects\AWS-CLOUD\.env
```

Đổi cấu hình database local từ Docker (`localhost:5434`) sang cổng tunnel (`127.0.0.1:15437`):

```dotenv
# Kết nối AWS RDS qua SSM Tunnel trên máy Windows
DATABASE_URL=postgresql+psycopg2://learncloud_admin:<URL_ENCODED_RDS_PASSWORD>@127.0.0.1:15437/learncloud?sslmode=require
```

**Quan trọng:**

- Thay toàn bộ `<URL_ENCODED_RDS_PASSWORD>` bằng mật khẩu PostgreSQL RDS thật đã URL-encode; **không giữ nguyên dấu `< >`**.
- **Không dùng nhầm mật khẩu pgAdmin** (mật khẩu mở phần mềm pgAdmin).
- Nếu mật khẩu có ký tự đặc biệt như `@`, `#`, `:`, `/`, `%`, phải **URL-encode** trước khi nhúng vào URL.
- Không commit `.env`; nên có `.env.example` chỉ chứa placeholder.
- Giữ `sslmode=require` cho kết nối TLS. Đối với production, nên cân nhắc xác thực chứng chỉ máy chủ qua CA phù hợp.

### URL-encode mật khẩu mà không ghi ra mã nguồn

Từ PowerShell tại thư mục gốc repo, sử dụng Python sẵn có:

```powershell
@'
import getpass
from urllib.parse import quote

password = getpass.getpass("RDS PostgreSQL password: ")
print(quote(password, safe=""))
'@ | python -
```

Copy kết quả (đã mã hóa cho URL) vào vị trí `<URL_ENCODED_RDS_PASSWORD>` của `.env`. **Kết quả này vẫn là secret, không chia sẻ.**

### Khuyến nghị cho nhóm

- Duy trì **hai cấu hình** trong tài liệu `.env.example`: local Docker và RDS tunnel; mỗi cá nhân bật đúng *một* `DATABASE_URL` trong `.env` riêng.
- Không dùng RDS chung để tự do chạy `DROP TABLE`, xóa dữ liệu, seed lại, hay chạy migration chưa được thống nhất.
- Các biến `.env` khác (AWS/S3/JWT...) giữ theo hợp đồng cấu hình thực tế của project; không tự ý đổi tên biến khi chưa kiểm tra code settings.

## 6. Khởi động lại FastAPI và kiểm thử

Nếu backend đang chạy, nhấn `Ctrl+C` để dừng, sau đó **khởi động lại** để đọc `.env` mới:

```powershell
cd "D:\projects\main projects\AWS-CLOUD\backend"
uvicorn app.main:app --reload
```

> Nếu virtual environment chưa được kích hoạt, hãy kích hoạt `.venv` của repo hoặc dùng lệnh Python tương ứng theo hướng dẫn setup của nhóm.

Truy cập Swagger UI:

```text
http://localhost:8000/docs
```

Gọi:

```http
GET /courses
```

**Kết quả kiểm chứng ngày 31/10/2026:**

```text
GET /courses -> 200
GET /courses HTTP/1.1" 200 OK
```

API trả `200 OK` xác nhận FastAPI đã xác thực và đọc dữ liệu qua kết nối RDS. Thời gian phản hồi khi đi qua SSM Tunnel có thể cao hơn khi dùng PostgreSQL local.

### Kiểm tra dữ liệu bằng pgAdmin (không bắt buộc)

Nếu đã cài pgAdmin, cấu hình kết nối server:

| Thuộc tính | Giá trị |
|---|---|
| Host | `127.0.0.1` |
| Port | `15437` |
| Maintenance database | `learncloud` |
| Username | `learncloud_admin` |
| Password | **Mật khẩu PostgreSQL RDS**, không phải master password của pgAdmin |
| SSL mode | `require` |

Chạy truy vấn chỉ đọc:

```sql
SELECT current_database(), current_user;
SELECT COUNT(*) AS total_courses FROM courses;
SELECT COUNT(*) AS total_lessons FROM lessons;
SELECT version FROM schema_migrations ORDER BY version;
```

Tại thời điểm đồng bộ dữ liệu (31/10/2026): `courses = 4`, `lessons = 12`; migration đã triển khai có `0001`, `0002`, `0004`, `0005`. Dữ liệu có thể thay đổi sau đó.

## 7. Chẩn đoán lỗi thường gặp

| Triệu chứng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| `Failed to connect` / `Connection refused` tới `127.0.0.1:15437` | Chưa mở tunnel, tunnel đã đóng hoặc sai cổng | Mở lại SSM session, chạy `Test-NetConnection` |
| `AccessDeniedException` khi `aws ssm start-session` | IAM identity chưa có quyền SSM cần thiết | Nhờ người quản trị cấp đúng quyền tới EC2/SSM document; không dùng chung access key |
| `TargetNotConnected` | EC2 hoặc SSM Agent chưa online | Kiểm tra instance đang chạy, role EC2 và Systems Manager |
| `password authentication failed for user "learncloud_admin"` | **Sai mật khẩu RDS** hoặc chuỗi URL phân tích mật khẩu sai | Xác minh mật khẩu PostgreSQL; kiểm tra URL-encoding; khởi động lại Uvicorn |
| pgAdmin đăng nhập được nhưng FastAPI báo sai password | pgAdmin có thể lưu mật khẩu khác với `.env` | Kiểm tra `.env`; thử kết nối `psycopg2` trực tiếp bằng mật khẩu nhập thủ công |
| `relation "courses" does not exist` | Chọn nhầm DB/schema hoặc chưa đồng bộ dữ liệu | Kiểm tra `dbname=learncloud`, `schema_migrations` và dữ liệu đích |
| Swagger trả `500 Internal Server Error` | Nhiều nguyên nhân có thể xảy ra | **Đọc traceback trong terminal Uvicorn**, không suy luận chỉ từ mã 500 |

### Kiểm tra độc lập mật khẩu RDS bằng Python

Đoạn dưới đây **không dùng** `DATABASE_URL`, giúp phân biệt lỗi mật khẩu với lỗi cấu hình URL. Giữ tunnel mở rồi chạy từ môi trường Python có `psycopg2`:

```powershell
@'
import getpass
import psycopg2

password = getpass.getpass("RDS PostgreSQL password: ")
try:
    with psycopg2.connect(
        host="127.0.0.1",
        port=15437,
        dbname="learncloud",
        user="learncloud_admin",
        password=password,
        sslmode="require",
        connect_timeout=10,
    ) as connection:
        print("SUCCESS: RDS authentication OK")
except psycopg2.Error as error:
    print("FAILED:", error)
'@ | python -
```

- `SUCCESS`: mật khẩu nhập trực tiếp dùng được. Kiểm tra `.env` và cách backend đọc `DATABASE_URL`.
- `FAILED` với `password authentication failed`: mật khẩu nhập không được RDS chấp nhận. Liên hệ người quản trị để xác nhận/đặt lại; không đoán nhiều lần.

**Không paste password, `.env` đầy đủ hoặc connection URL có secret vào issue, ảnh chụp màn hình hay log gửi nhóm.**

## 8. Phân biệt các loại mật khẩu

| Loại | Dùng cho | Có đặt vào `DATABASE_URL`? |
|---|---|---|
| **AWS RDS / PostgreSQL user password** | Xác thực user `learncloud_admin` hoặc user ứng dụng với PostgreSQL | **Có** (qua cấu hình bảo mật phù hợp) |
| **pgAdmin master password** | Mở/giải mã thông tin lưu trong pgAdmin | **Không** |
| **AWS IAM access key / credentials** | Được phép mở SSM session | **Không** |

## 9. Lưu ý khi làm việc chung và triển khai tiếp

- **SSM Tunnel chỉ hỗ trợ truy cập từ máy developer**, không phải endpoint PostgreSQL chung của hệ thống.
- Khi Lambda hoặc backend được triển khai bên trong AWS VPC, ứng dụng phải kết nối bằng **RDS private endpoint và security group phù hợp**, **không dùng `127.0.0.1:15437`**.
- Không mở `Public access=Yes` hoặc cho inbound RDS `5432` từ `0.0.0.0/0` chỉ để tiện phát triển.
- Giữ DB Docker local làm môi trường phát triển độc lập; chỉ kết nối RDS chung khi thật sự cần tích hợp AWS.
- Dừng SSM session khi không sử dụng, và nhớ rằng EC2/RDS đang chạy có thể phát sinh chi phí AWS.

## 10. Checklist để mỗi thành viên tự xác nhận

- [ ] AWS profile cá nhân đã xác thực (`aws sts get-caller-identity`).
- [ ] Có quyền dùng SSM với EC2 bridge.
- [ ] Cửa sổ SSM đang mở và `Test-NetConnection` trả `True`.
- [ ] `.env` dùng RDS username/password hợp lệ, không còn placeholder, cổng `15437`, `sslmode=require`.
- [ ] Đã khởi động lại FastAPI sau khi thay `.env`.
- [ ] Swagger `GET /courses` trả `200 OK`.
- [ ] Không đẩy `.env` hoặc secret lên repository.

---

**Đề xuất vị trí trong repository:** `docs/FASTAPI_RDS_CONNECTION_GUIDE.md`.

**Ghi chú:** Tài liệu phản ánh kết nối đã thực hiện và kiểm chứng ngày 31/10/2026. Nếu nhóm thay đổi AWS account, region, RDS endpoint, EC2 bridge hoặc quy định cấp quyền, cần cập nhật các thông số tương ứng.
