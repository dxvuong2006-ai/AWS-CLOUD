# Thiết lập môi trường local

Các bước này dành cho máy phát triển và dữ liệu local được cô lập. Chúng không deploy hoặc kết nối AWS. Không trỏ test hay migration command tới RDS.

## Yêu cầu

- Python 3.11 trở lên và pip.
- Node.js/npm tương thích với `frontend/package-lock.json`.
- Chỉ cần Docker Desktop nếu muốn chạy PostgreSQL/Mailpit local.

## Backend

Mở PowerShell tại thư mục gốc repository:

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
```

Đặt `DATABASE_URL` trỏ tới database local hoặc SQLite test cô lập; cấu hình secret chỉ dành cho development theo yêu cầu trong `backend/app/config.py`. Không sao chép file môi trường production. Backend không khởi động nếu `DATABASE_URL` rỗng.

Khởi động backend từ thư mục gốc:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

Mở `http://127.0.0.1:8000/docs` để xem OpenAPI runtime hoặc `http://127.0.0.1:8000/health` để gọi health route.

## Frontend

Mở terminal thứ hai:

```powershell
Set-Location .\frontend
npm.cmd ci
npm.cmd run dev
```

Vite mặc định phục vụ ứng dụng tại `http://localhost:5173`. Dùng `frontend/.env.example` để xem tên biến cấu hình. Mọi biến `VITE_*` đều được đưa vào bundle trình duyệt; không đặt secret tại đây.

## Dịch vụ local tùy chọn

`docker-compose.yml` định nghĩa PostgreSQL 16 tại host port `5434` và Mailpit tại `1025`/`8025`. Chỉ khởi động khi cần:

```powershell
docker compose up -d learncloud-db mailpit
```

Với database local mới, đọc `database/migrations/README.md` và lưu ý các version migration lịch sử bị trùng trước khi áp dụng schema/migration. Compose volume có thể chứa dữ liệu local; không dùng `down -v` để dọn thường xuyên.

## Kiểm thử và giới hạn

Backend có PostgreSQL gate rõ ràng; xem [báo cáo regression đã lưu](operations/backend-regression-report.md). Báo cáo ghi nhận 463 pass và 69 skip trong lượt chạy offline với SQLite. Các case PostgreSQL bị skip vẫn chưa được xác minh cho tới khi chạy trên database test riêng.

Frontend có các lệnh `npm.cmd test`, `npm.cmd run build`, `npm.cmd run test:browser`, `npm.cmd run test:auth-browser` từ thư mục `frontend/`. AI pipeline có test trong `ai_pipeline/tests/`; xem `ai_pipeline/README.md` để biết lệnh local chính xác. Hướng dẫn này không tự chạy test suite.

## Xác thực và an toàn

Backend dùng bearer access token. Local auth là chế độ riêng, phải bật rõ ràng cho development/test; không thay thế Cognito/AWS trong production. Chỉ dùng tài khoản seed/test local. Không dùng các hướng dẫn `X-Demo-User` cũ trong ghi chú lưu trữ để bỏ qua xác thực. Không commit `.env`, `frontend/.env`, token hay mật khẩu test lên Git.
