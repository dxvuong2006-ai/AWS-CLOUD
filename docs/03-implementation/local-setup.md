# Thiết lập môi trường local

Tài liệu này hướng dẫn chạy LearnCloud cô lập trên máy phát triển. Các bước không deploy AWS, không chạy migration trên RDS và không yêu cầu credential AWS cho smoke test cơ bản.

## Yêu cầu

- Python 3.11+ (repository và Lambda template hướng tới Python 3.12).
- Node.js/npm tương thích `frontend/package-lock.json`.
- Docker Desktop chỉ khi dùng PostgreSQL 16/Mailpit từ Compose.
- PowerShell cho các lệnh bên dưới.

## Cài dependency

Từ root repository:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt

Push-Location .\frontend
npm.cmd ci
Pop-Location
```

Không sao chép file `.env` từ môi trường khác. `.env.example` và `frontend/.env.example` chỉ là danh mục biến/placeholder; mọi file `.env` thực phải được giữ ngoài Git.

## Lựa chọn A - smoke test backend với SQLite

Phù hợp để xem health/OpenAPI và phát triển cô lập. Khi khởi động, FastAPI tạo các bảng SQLAlchemy còn thiếu trong SQLite; cơ chế này không chạy với PostgreSQL.

```powershell
$env:DATABASE_URL = 'sqlite:///./backend/tests.db'
$env:APP_ENV = 'development'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

Xác minh:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Start-Process http://127.0.0.1:8000/docs
```

Kết quả health mong đợi là JSON `{"status":"ok"}`. Điều này chỉ chứng minh tiến trình local khởi động.

## Lựa chọn B - PostgreSQL 16 local

Compose định nghĩa database ở host port `5434` và Mailpit ở `1025`/`8025`:

```powershell
docker compose up -d learncloud-db mailpit
docker compose ps
```

Giá trị development cụ thể được giữ trong `docker-compose.yml`; không sao chép password đó vào docs/issue. Tạo `.env` local từ placeholder và trỏ `DATABASE_URL` tới `127.0.0.1:5434`.

Với database trống, `database/schema.sql` là snapshot bootstrap, nhưng không bao phủ toàn bộ bảng bổ sung trong models/migrations. Trước khi nạp schema/seed hoặc migration, đọc [thiết kế database](../02-architecture/database-design.md) và [migration README](../../database/migrations/README.md); không dùng lệnh “apply all” vì có các nhánh `0004` lịch sử.

Tối thiểu cho database test riêng đã được review:

1. Xác nhận đúng container/database local.
2. Nạp `schema.sql` và kiểm tra registry.
3. Chọn chính xác migration bổ sung theo preflight/runbook, không chạy RDS chung.
4. Chỉ nạp `seed.sql` nếu database là dữ liệu local có thể bỏ.

Không dùng `docker compose down -v` trừ khi chủ dữ liệu chủ động muốn xóa volume local.

## Xác thực local

Mặc định backend không bật local auth. Để dùng API auth local trong development:

```powershell
$env:APP_ENV = 'development'
$env:LOCAL_AUTH_ENABLED = 'true'
$env:LOCAL_AUTH_JWT_SECRET = '<generate-a-random-local-secret>'
```

Frontend dùng tên cờ lịch sử `VITE_USE_AUTH_MOCK`; giá trị `true` hiện nay nghĩa là **FastAPI local auth thật**, không phải mock token:

```dotenv
VITE_API_URL=http://127.0.0.1:8000
VITE_USE_MOCK=false
VITE_USE_AUTH_MOCK=true
```

Mailpit nhận OTP local tại SMTP `127.0.0.1:1025`; giao diện xem thư là `http://127.0.0.1:8025`. Không ghi OTP/email/password test vào GitHub.

Để dùng Cognito, đặt `VITE_USE_AUTH_MOCK=false` và cung cấp Region/User Pool/App Client public trong file local. Luồng này phụ thuộc AWS và không phải smoke test offline.

## Chạy frontend

```powershell
Set-Location .\frontend
npm.cmd run dev
```

Vite mặc định phục vụ `http://localhost:5173`. API client cũng chấp nhận `VITE_API_BASE_URL` và chuẩn hóa `localhost` sang IPv4 loopback cho backend local.

### UI mock hoàn toàn

`VITE_USE_MOCK=true` dùng dữ liệu mock và không chứng minh backend/PostgreSQL/AWS. Chế độ này hữu ích cho demo giao diện nhưng phải nói rõ khi trình bày.

## Video và AI local

- `VIDEO_PROCESSOR_BACKEND=disabled`, `VIDEO_PIPELINE_ENABLED=false`, `VIDEO_AI_ENABLED=false`, `AI_WORKER_ENABLED=false` là mặc định an toàn.
- Adapter local/fixture có thể hỗ trợ test nghiệp vụ; không tự transcode video hay chứng minh Bedrock/Transcribe.
- Không bật EventBridge/MediaConvert/Bedrock bằng credential production từ máy local chỉ để demo.

## Smoke test và test offline

```powershell
.\.venv\Scripts\python.exe backend\tests\run_unit_offline.py
.\.venv\Scripts\python.exe backend\tests\run_auth_offline.py
.\.venv\Scripts\python.exe -m unittest discover -s ai_pipeline\tests -p 'test_*.py'

Push-Location .\frontend
npm.cmd test
Pop-Location
```

Kết quả đo ngày 17/11/2026 được ghi trong [tài liệu kiểm thử](../04-evaluation/testing.md). Các PostgreSQL gate phải dùng database test loopback chuyên dụng; không thay biến test bằng RDS/application `DATABASE_URL`.

## Dừng dịch vụ

Dừng Uvicorn/Vite bằng `Ctrl+C`. Dừng container mà không xóa dữ liệu:

```powershell
docker compose stop
```
