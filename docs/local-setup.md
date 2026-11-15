# Thiết lập môi trường local

Tài liệu này dùng cho môi trường phát triển/test cô lập. Không dùng RDS,
credential AWS production hoặc database dùng chung. Các lệnh dưới đây không
chạy migration và không thay đổi AWS.

## 1. Điều kiện cần

- Python 3.11+ và `pip`.
- Node.js/npm tương thích với `frontend/package-lock.json`.
- Docker Desktop chỉ khi cần PostgreSQL local.
- Các cổng `5434`, `8000`, `5173` còn trống nếu dùng cấu hình mặc định.

AWS CLI không cần cho regression offline. Chỉ cấu hình AWS trong một đợt test
riêng đã được phê duyệt; không dùng profile production để chạy test.

## 2. Cấu hình local

Từ root repository:

```powershell
Copy-Item .env.example .env
```

Chỉ điền giá trị local. Không commit `.env`. Với backend offline, tối thiểu cần
`DATABASE_URL` và các secret local đủ dài theo validation trong
`backend/app/config.py`. Frontend dùng `frontend/.env.example` làm danh sách
biến; các biến bắt đầu bằng `VITE_` được đưa vào bundle trình duyệt nên không
được chứa secret.

## 3. Cài backend

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
```

Chạy từ root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

Kiểm tra health và OpenAPI:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Start-Process http://127.0.0.1:8000/docs
```

## 4. Cài frontend

```powershell
Set-Location .\frontend
npm.cmd ci
npm.cmd run dev
```

Mở `http://localhost:5173`. Để kiểm tra trước bàn giao:

```powershell
npm.cmd test
npm.cmd run build
```

`frontend/dist/` là build artifact và không được commit.

## 5. Backend regression offline

Chạy từ `backend/`. Cấu hình này dùng SQLite in-memory, credential giả và bỏ
AWS profile khỏi tiến trình; không gọi AWS/RDS:

```powershell
$env:DATABASE_URL = "sqlite:///:memory:"
$env:AWS_ACCESS_KEY_ID = "testing"
$env:AWS_SECRET_ACCESS_KEY = "testing"
Remove-Item Env:AWS_PROFILE -ErrorAction SilentlyContinue
Remove-Item Env:AWS_DEFAULT_PROFILE -ErrorAction SilentlyContinue
python -m pytest tests -q -rs -p no:cacheprovider
```

Các suite PostgreSQL opt-in sẽ skip nếu không có database test chuyên dụng.
Đây là hành vi có chủ đích, không phải bằng chứng các case đó đã pass. Danh sách
gate/port/database guard nằm trong `BACKEND_REGRESSION_REPORT.md`.

## 6. PostgreSQL local và migration safety

Khởi động database local nếu cần:

```powershell
docker compose up -d learncloud-db
docker compose ps
```

Không tự động áp dụng toàn bộ `database/migrations/`: repository có lịch sử
migration cần kế hoạch reconcile và các integration test có guard riêng. Trước
mọi thao tác schema, đọc `database/migrations/README.md`, dùng database local
cô lập, chụp trạng thái ban đầu và xác nhận target không phải RDS/production.

Các file trong `database/checks/` là preflight/postflight để review. Không chạy
chúng như migration. Cleanup repository không chạy SQL nào.

## 7. Đăng nhập local

Backend hỗ trợ các luồng auth được mô tả trong `docs/api-contract.md`. Không
dùng `X-Demo-User` cho route bảo vệ. Khi cần provision mật khẩu local cho đúng
tài khoản test, dùng script tương tác và chỉ trên database test đã xác minh:

```powershell
Set-Location .\backend
python scripts/set_user_password.py --email EMAIL_TEST
```

Script không có mật khẩu mặc định; không ghi password vào command history,
source, fixture hoặc báo cáo.

## 8. Lỗi thường gặp

| Hiện tượng | Kiểm tra an toàn |
| --- | --- |
| `connection refused` tới `5434` | `docker compose ps` và healthcheck của `learncloud-db`. |
| Thiếu dependency Python | Cài lại `backend/requirements.txt` trong `.venv`. |
| `ProfileNotFound` khi chạy test | Gỡ `AWS_PROFILE`/`AWS_DEFAULT_PROFILE` khỏi tiến trình test. |
| npm bị PowerShell policy chặn | Dùng `npm.cmd`, không cần đổi execution policy. |
| `401`/`403` | Xác minh đúng auth mode, token test và role; không bypass bằng header demo. |
| PostgreSQL test bị skip | Đọc guard của suite; không trỏ sang RDS để ép chạy. |

## 9. Dừng môi trường

```powershell
docker compose down
```

Lệnh này giữ volume local. Việc xóa volume/backup phải được người sở hữu dữ liệu
phê duyệt riêng; không nằm trong quy trình cleanup repository.
