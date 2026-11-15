# LearnCloud

LearnCloud là nền tảng học cloud theo hướng video-first, gồm React/Vite,
FastAPI/PostgreSQL, xác thực Cognito, xử lý video bất đồng bộ và các chức năng
AI Tutor/analytics. Region AWS chính của dự án là `ap-southeast-1`.

## Baseline bàn giao ngày 15/11/2026

- Frontend đã được triển khai qua S3/CloudFront.
- Backend đang chạy trên Lambda version 6 theo thông tin bàn giao của nhóm.
- Hotfix Admin/Cognito dùng `users.cognito_sub` làm Cognito `Username` đã có
  trong source và package Lambda local.
- Backend regression gần nhất: 464 pass, 0 fail, 69 skip. Nhóm skip là các gate
  PostgreSQL cần database test cô lập; không được diễn giải là đã pass.

Các dòng trên mô tả baseline bàn giao, không thay cho kiểm tra cấu hình AWS.
Khi cần audit deployment, đối chiếu inventory mới nhất trong `agent/input/` và
không suy trạng thái AWS chỉ từ source hoặc tài liệu thiết kế.

## Cấu trúc repository

| Đường dẫn | Vai trò |
| --- | --- |
| `frontend/` | React/Vite, API client và frontend tests. |
| `backend/` | FastAPI, service/repository, Lambda entry point và backend tests. |
| `ai_pipeline/` | Pipeline AI/video của Tuấn; giữ nguyên ownership và lịch sử. |
| `database/` | Schema, migrations, preflight/postflight checks và DB test fixtures. |
| `infrastructure/` | Cấu hình mẫu cho Lambda, IAM, EventBridge và Step Functions. |
| `docs/` | API contract, setup, deployment runbook và tài liệu vận hành. |
| `agent/input/` | Tài liệu đầu vào/inventory được cung cấp cho các đợt audit. |
| `agent/output/` | Báo cáo có bằng chứng; không dùng thay source hoặc deployment state. |

## Thiết lập nhanh

Yêu cầu: Python 3.11+, Node.js/npm và PostgreSQL cô lập hoặc Docker Desktop nếu
cần kiểm tra database local.

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt

Set-Location .\frontend
npm.cmd ci
npm.cmd run dev
```

Chạy backend từ root repository trong một terminal khác:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

Không trỏ test vào RDS/production. Không tự động chạy migration; đọc
[hướng dẫn local](docs/local-setup.md) và
[quy ước migration](database/migrations/README.md) trước khi chuẩn bị database
test riêng.

## Kiểm tra trước khi bàn giao

Backend regression offline, chạy từ `backend/` với AWS profile bị loại khỏi
tiến trình và database SQLite in-memory:

```powershell
$env:DATABASE_URL = "sqlite:///:memory:"
$env:AWS_ACCESS_KEY_ID = "testing"
$env:AWS_SECRET_ACCESS_KEY = "testing"
Remove-Item Env:AWS_PROFILE -ErrorAction SilentlyContinue
python -m pytest tests -q -rs -p no:cacheprovider
```

Frontend, chạy từ `frontend/`:

```powershell
npm.cmd test
npm.cmd run build
```

Các test PostgreSQL opt-in chỉ được bật với database loopback chuyên dụng đúng
guard của từng suite. Xem [báo cáo regression](BACKEND_REGRESSION_REPORT.md) để
biết các gate và giới hạn đã xác minh.

## Bản đồ tài liệu

| Tài liệu | Phạm vi |
| --- | --- |
| [Requirements](docs/requirements.md) | Yêu cầu sản phẩm; không phải bằng chứng implementation. |
| [Architecture](architecture.md) | Kiến trúc và ownership mục tiêu. |
| [API contract](docs/api-contract.md) | Contract API giữa frontend/backend. |
| [Local setup](docs/local-setup.md) | Cài dependencies, chạy local và test an toàn. |
| [Database](docs/database.md) | Mô hình dữ liệu và ràng buộc. |
| [Migrations](database/migrations/README.md) | Lịch sử, guard và quy trình migration. |
| [AWS deployment](docs/aws-deployment.md) | Runbook tham chiếu; không phải inventory hiện tại. |
| [AWS API gate](docs/aws-api-gate.md) | Checklist/gate cho API Lambda và Cognito. |
| [K4-K5 rollout](docs/k4-k5-production-rollout.md) | Runbook rollout pipeline/AI có kiểm soát. |

Tài liệu lịch sử kiểm thử trong `agent/output/` và
`BACKEND_REGRESSION_REPORT.md` được giữ để truy vết. Các file thiết kế `.docx`,
PDF inventory và ảnh UI không được coi là bằng chứng chức năng nếu chưa có test
hoặc xác minh deployment tương ứng.

## Quy tắc an toàn

- Không commit `.env`, credential, token, private key, presigned URL hoặc dữ
  liệu production.
- Không commit package Lambda ZIP, cache, log, database test hoặc output build.
- Không sửa migration đã merge; tạo migration mới sau khi review tác động.
- Backend quyết định role, ownership, enrollment, unlock và account status.
- Không deploy, chạy migration hoặc thay đổi AWS từ quy trình cleanup repository.
