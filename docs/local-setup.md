# Thiết lập môi trường local

Tài liệu này hướng dẫn khởi tạo một môi trường LearnCloud sạch trên Windows
PowerShell. Docker Compose chỉ chạy PostgreSQL; backend và frontend chạy trực
tiếp trên máy phát triển.

## 1. Điều kiện cần

- Docker Desktop đang chạy và có Docker Compose v2 (`docker compose version`).
- Python 3.11+ và `pip`.
- Node.js LTS và npm.
- Cổng `5434`, `8000`, `5173` chưa bị ứng dụng khác chiếm.

AWS CLI/credential **không cần** để chạy course flow local. Chỉ cần chúng khi
gọi route tạo S3 presigned upload URL.

## 2. Tạo cấu hình local

Từ thư mục gốc repository, tạo `.env` từ mẫu nếu chưa có:

```powershell
Copy-Item .env.example .env
```

Mở `.env` và đặt tối thiểu các giá trị sau. Mật khẩu database phải khớp với
`docker-compose.yml`; không commit file này.

```dotenv
DATABASE_URL=postgresql://learncloud:learncloud_dev_password@localhost:5434/learncloud
JWT_SECRET_KEY=replace-with-a-local-random-secret-at-least-32-characters
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60

# Chỉ cần khi thử upload S3; config backend hiện dùng tên S3_BUCKET.
S3_BUCKET=learncloud-videos-mentorcloud
AWS_REGION=ap-southeast-1
```

> `.env.example` còn có một số biến dành cho kế hoạch mở rộng. Backend hiện
> yêu cầu `DATABASE_URL` và `JWT_SECRET_KEY`; `S3_BUCKET`/`AWS_REGION` có giá
> trị mặc định nhưng nên khai báo rõ khi dùng S3.

## 3. Khởi động và nạp database

```powershell
docker compose up -d learncloud-db
docker compose ps
```

Chờ service có trạng thái `healthy`, sau đó nạp schema, migration tương thích
database cũ và dữ liệu demo theo thứ tự:

```powershell
Get-Content .\database\schema.sql -Raw |
  docker exec -i learncloud-db psql -v ON_ERROR_STOP=1 -U learncloud -d learncloud

Get-Content .\database\migrations\0003_reconcile_legacy_schema.sql -Raw |
  docker exec -i learncloud-db psql -v ON_ERROR_STOP=1 -U learncloud -d learncloud

Get-Content .\database\seed.sql -Raw |
  docker exec -i learncloud-db psql -v ON_ERROR_STOP=1 -U learncloud -d learncloud
```

Schema và migration có thể chạy lại an toàn; migration chỉ thêm cột còn thiếu,
không xóa dữ liệu hiện có. Không xóa volume để xử lý lỗi schema nếu cần giữ dữ
liệu local.

Xác minh dữ liệu:

```powershell
docker exec learncloud-db psql -U learncloud -d learncloud -c "SELECT id, email, role FROM users ORDER BY id;"
docker exec learncloud-db psql -U learncloud -d learncloud -c "SELECT id, title, status FROM courses ORDER BY id;"
```

Seed tạo một instructor `instructor@example.com` và hai student; cả hai
student được enrollment vào course `Introduction to AWS` đã publish. ID không
nên được hard-code ngoài database sạch; tra cứu ID bằng các lệnh ở kịch bản
demo.

## 4. Chạy backend

Tạo virtual environment (một lần) và cài dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
```

Khởi động FastAPI từ thư mục gốc:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

Kiểm tra bằng một PowerShell khác:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Kết quả mong đợi là `status : ok`. Swagger UI nằm tại
`http://127.0.0.1:8000/docs`.

## 5. Chạy frontend

Mở một PowerShell khác:

```powershell
Set-Location .\frontend
npm.cmd install
npm.cmd run dev
```

Dùng `npm.cmd` trên Windows nếu PowerShell chặn `npm.ps1` theo execution
policy. Mở `http://localhost:5173` sau khi Vite thông báo URL local.

Để kiểm tra build production mà không chạy server dev:

```powershell
Set-Location .\frontend
npm.cmd run build
```

## 6. Smoke test API và user demo

Danh sách course đã publish không cần header:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/courses
```

Các route nghiệp vụ local hiện nhận `X-Demo-User`. Ví dụ, instructor tạo
course nháp:

```powershell
$instructorId = (docker exec learncloud-db psql -U learncloud -d learncloud -tAc "SELECT id FROM users WHERE email = 'instructor@example.com'").Trim()
$headers = @{ "X-Demo-User" = $instructorId }
$body = @{ title = "Local test course"; description = "Created locally"; learning_objectives = @("Verify setup") } | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8000/courses -Method Post -Headers $headers -ContentType "application/json" -Body $body
```

`X-Demo-User` chỉ là cách giả lập danh tính trong môi trường local. Không đưa
header này hoặc API hiện tại ra môi trường công khai.

## 7. Reset database local

Chỉ dùng khi bạn đồng ý xóa toàn bộ dữ liệu trong volume local:

```powershell
docker compose down -v
docker compose up -d learncloud-db
```

Chờ database healthy rồi lặp lại mục 3. Không dùng `down -v` trên môi trường
dùng chung hoặc RDS.

## 8. Lỗi thường gặp

| Hiện tượng | Cách xử lý |
| --- | --- |
| `connection refused` tới cổng 5434 | Chạy `docker compose ps`, xem `docker compose logs learncloud-db`, rồi chờ healthcheck xanh. |
| Backend báo thiếu `DATABASE_URL` hoặc `JWT_SECRET_KEY` | Kiểm tra `.env` nằm ở root và `JWT_SECRET_KEY` dài ít nhất 32 ký tự. |
| API báo thiếu cột như `courses.created_at` | Nạp lại `database/schema.sql`, sau đó áp dụng migration `0003_reconcile_legacy_schema.sql` như mục 3; không cần xóa volume. |
| `psycopg2`/Python dependency lỗi | Kích hoạt lại `.venv`, nâng pip, sau đó cài lại `backend/requirements.txt`. |
| `npm` bị policy chặn | Dùng `npm.cmd` như mục 5, không cần đổi execution policy của máy. |
| `401`/`403` khi gọi API | Dùng ID có thật trong header `X-Demo-User` và đúng role (instructor cho create/update; student cho enroll). |
| Route kỳ vọng progress/quiz/Tutor trả `404` | Những router này chưa được đăng ký đầy đủ trong backend hiện tại; xem README để biết phạm vi chạy được. |

## 9. Dừng môi trường

```powershell
docker compose down
```

Lệnh này giữ volume dữ liệu. Dừng server FastAPI/Vite bằng `Ctrl+C` trong từng
terminal.


## Đăng nhập JWT và kiểm tra mục 1–3 (04/11/2026)

1. Chuẩn bị PostgreSQL, migration password_hash và seed theo phần hướng dẫn trên.
2. Cài backend/requirements.txt. Đặt DATABASE_URL và JWT_SECRET_KEY (ít nhất 32 ký tự bí mật)
   trong file .env ở gốc repository. Không commit giá trị bí mật.
3. Từ thư mục backend, đặt mật khẩu cho tài khoản seed qua:
   python scripts/set_user_password.py --email EMAIL_SEED
   Script hỏi mật khẩu tương tác; không có mật khẩu mặc định trong source.
4. Chạy uvicorn app.main:app --reload. Frontend cần VITE_API_URL=http://localhost:8000.
5. VITE_USE_MOCK=true vẫn yêu cầu đăng nhập backend, nhưng nội dung/tiến độ/quiz dùng mock.
   VITE_USE_MOCK=false chưa có đầy đủ video/quiz/progress runtime, xem api-contract.md.
6. Mở /login, thử từng vai trò. Không dùng X-Demo-User; API bảo vệ không nhận header đó.

Frontend: npm test và npm run build.
Backend (thư mục backend): python -m unittest discover -s tests/unit -p test_auth_integration.py -v
Bộ test auth dùng repository giả và HTTP ASGI trong bộ nhớ, không sửa database thật.

Reset mock: về trang danh sách, F12 Console rồi chạy:
```js
const session = JSON.parse(sessionStorage.getItem("learncloud.auth.session"));
const userId = session?.user?.id;
if (userId != null) {
  localStorage.removeItem("learncloud.mock.progress.v2:user:" + userId);
  localStorage.removeItem("learncloud.mock.attempts:user:" + userId);
  location.reload();
}
```
Dữ liệu cũ chưa gắn user không được chuyển tự động sang tài khoản mới.
Ngưỡng video mock hiện giữ 10% phục vụ test; giá trị dự kiến chính thức là 95%.
