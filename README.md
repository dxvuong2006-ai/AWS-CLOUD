# LearnCloud

LearnCloud là nền tảng học trực tuyến lấy video làm trung tâm, tích hợp trí tuệ nhân tạo (AI) để hỗ trợ quá trình học tập. Dự án bao gồm Frontend React/Vite, Backend FastAPI, cơ sở dữ liệu PostgreSQL cùng hệ thống xử lý video và sinh nội dung AI, hỗ trợ chạy trên môi trường local và AWS.

## 1. Cấu trúc dự án

| Thư mục | Chức năng |
|---|---|
| `frontend/` | Giao diện React/Vite, tích hợp xác thực, API và kiểm thử trình duyệt. |
| `backend/` | FastAPI, các API, services, repositories, adapters và bộ kiểm thử. |
| `ai_pipeline/` | Xử lý transcript, sinh nội dung AI, schemas, dữ liệu mẫu và kiểm thử. |
| `database/` | Khởi tạo PostgreSQL, migrations, scripts kiểm tra và dữ liệu mẫu. |
| `infrastructure/` | Cấu hình AWS, đóng gói Lambda và các ví dụ triển khai. |
| `docs/` | Tài liệu dự án, hướng dẫn cài đặt, triển khai và vận hành. |

## 2. Chạy dự án trên máy local

Xem [hướng dẫn cài đặt](docs/local-setup.md) để biết các yêu cầu về môi trường, cấu hình cơ sở dữ liệu và xác thực.

Backend cần biến môi trường `DATABASE_URL` để kết nối PostgreSQL. Các biến `VITE_*` của Frontend được sử dụng trong trình duyệt, vì vậy không được chứa thông tin bí mật.

**Bước 1: Cài đặt môi trường và dependencies**

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
Set-Location .\frontend
npm.cmd ci
npm.cmd run dev
```

**Bước 2: Khởi chạy Backend**

Mở Terminal thứ hai tại thư mục gốc của dự án:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

## 3. Tài liệu dự án

Xem [docs/README.md](docs/README.md) để tra cứu danh sách tài liệu và quy ước xác minh thông tin.

Các tài liệu chính:

- [Yêu cầu hệ thống](docs/requirements.md)
- [Kiến trúc hệ thống](docs/architecture.md)
- [Danh sách và đặc tả API](docs/api-contract.md)
- [Cơ sở dữ liệu](docs/database.md)
- [Hướng dẫn triển khai AWS](docs/aws-deployment.md)
- [Kịch bản demo](docs/demo-script.md)

## 4. Kiểm thử và lưu ý bảo mật

Sự tồn tại của source code hoặc cấu hình không đồng nghĩa với việc chức năng đã hoạt động thành công trên môi trường thực tế.

[Báo cáo kiểm thử Backend](docs/operations/backend-regression-report.md) ghi nhận kết quả của lần kiểm thử offline được lưu:

- **463 tests PASS**
- **0 tests FAIL**
- **69 tests SKIP** do yêu cầu môi trường PostgreSQL riêng.

Các trường hợp SKIP chưa được xác minh trên PostgreSQL và không được tính là kiểm thử thành công.

Trạng thái triển khai AWS Production chưa được xác minh trong quá trình dọn dẹp tài liệu.

**Lưu ý bảo mật:**

- Không commit `.env`, credentials, tokens, mật khẩu, private keys hoặc presigned URLs lên GitHub.
- Không chạy migrations hoặc triển khai AWS chỉ dựa trên các cấu hình ví dụ trong repository.
- Kiểm tra [lịch sử migration và các biện pháp an toàn](database/migrations/README.md) trước khi thực thi SQL.