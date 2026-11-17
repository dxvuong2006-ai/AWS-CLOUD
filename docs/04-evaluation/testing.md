# Kiểm thử


## Chiến lược

| Lớp | Mục tiêu | Môi trường |
|---|---|---|
| Unit/offline backend | Quy tắc role/ownership, upload/pipeline, review, quiz, progress, Tutor, adapters với double/stub | SQLite in-memory hoặc test doubles; socket ngoài bị chặn |
| Auth/P0 regression | Cognito/local auth, authorization, provisioning và account isolation | Pytest offline; PostgreSQL-gated cases được skip có chủ đích |
| Frontend unit/contract | API client, auth, course/enrollment, upload confirmation, quiz, progress, flashcard, route/gate helpers | Node built-in test runner; không browser/AWS |
| AI processors | Schema/fixture/processor và Tutor context | Python unittest; không gọi model thật |
| PostgreSQL integration | Constraint, transaction/savepoint, lock/concurrency, migration, ledger | PostgreSQL 16 test database loopback riêng; opt-in gate |
| Browser E2E | UI, Vite, backend và auth thật trong test environment | Cần browser và database test cô lập |
| AWS E2E | Cognito/API/S3/K4/K5/RDS/CloudWatch theo canary | Account/resource test được duyệt; log/execution có ngày |

## Kết quả tái hiện

Các lệnh dưới đây đã chạy từ working tree hiện tại trước khi chỉ sửa tài liệu; không truy cập AWS/RDS và không thay application source.

| Lượt chạy | Lệnh | Kết quả | Phạm vi/giới hạn |
|---|---|---:|---|
| Backend offline unit | `.\.venv\Scripts\python.exe backend\tests\run_unit_offline.py` | **173 pass, 0 fail** | `unittest` trong `backend/tests/unit`; fake AWS config và cấm socket ngoài |
| Auth/P0 offline | `.\.venv\Scripts\python.exe backend\tests\run_auth_offline.py` | **126 pass, 15 skip, 0 fail** | Năm module auth/P0; có 96 warnings; **chồng lặp** một phần với lượt backend, không cộng thành 299 |
| Frontend Node | `npm.cmd test` trong `frontend/` | **79 pass, 0 fail, 0 skip** | 19 file `*.test.cjs` được package script chọn; không gồm hai browser script |
| AI pipeline | `.\.venv\Scripts\python.exe -m unittest discover -s ai_pipeline\tests -p 'test_*.py'` | **11 pass, 0 fail** | Processor/context offline; không gọi Bedrock/Transcribe |

### 15 SKIP của lượt auth/P0

SKIP là các ca cần PostgreSQL/role/provisioning gate hoặc môi trường test chuyên biệt; chúng không phải PASS. Lượt chạy không bật biến opt-in và không thay `DATABASE_URL` bằng RDS/application database. Muốn chạy phải theo guard trong test, dùng database loopback riêng có thể xóa/rollback và quyền đã được review.

### Warnings

Lượt auth/P0 ghi 96 warnings, chủ yếu từ API deprecated của Starlette/HTTPX và các đường test cũ. Warnings không làm test fail nhưng là technical debt; không nên ẩn chúng để có bảng kết quả đẹp hơn.

## Số liệu


| Nhóm | Số liệu trong PDF | Cách diễn giải đúng |
|---|---:|---|
| Backend unit/regression giai đoạn video | 66/66 đạt | Snapshot lịch sử, một số tích hợp AWS dùng stub; không đại diện toàn suite hiện tại |
| PostgreSQL integration | 9/9 đạt | Snapshot lịch sử có transaction/savepoint/two-connection; không được tái hiện trong lượt docs này |
| HTTP nghiệp vụ | Các ca 200/409/401/403 trong bảng TC01–TC12 | Minh chứng theo báo cáo; exact endpoint/behavior phải đối chiếu source hiện tại |
| AWS video/AI đầu-cuối | 3/3 tới `REVIEW_REQUIRED` | Minh chứng theo báo cáo; không xác nhận pipeline AWS hiện tại |


## Báo cáo regression lịch sử trong repository

[Báo cáo backend regression lưu trữ](../archive/operations/backend-regression-report.md) ghi một lượt toàn suite offline trước đây: **463 pass, 69 skip, 0 fail** trên 532 test, với PostgreSQL gates tắt. Đây là bản ghi lịch sử có phạm vi rộng hơn runner 173 test ở trên; lượt cập nhật tài liệu hiện tại không chạy lại toàn lệnh pytest đó nên không nâng ngày của kết quả. 69 skip vẫn là khoảng chưa xác minh PostgreSQL.

## Ma trận nghiệp vụ cốt lõi

| Quy tắc | Test/source hiện có | Mức bằng chứng hiện tại |
|---|---|---|
| Student không tạo course | Authorization/backend và frontend role tests | Đã kiểm thử local |
| Enrollment không trùng | Service/DB unique và frontend enrollment tests | Local pass; PostgreSQL runtime hiện tại chưa xác minh |
| Upload cần PUT rồi confirm | Upload service và frontend upload tests | Local pass với doubles; S3 thật chưa xác minh |
| Nộp quiz idempotent | Request id/hash, replay/concurrent tests | Local pass; PostgreSQL concurrency gate chưa chạy lại |
| 49/50/79/80 | Quiz/remediation/unlock tests | Đã kiểm thử local |
| Section khóa từ backend | Access/unlock tests | Đã kiểm thử local |
| Nội dung chưa duyệt không public | Review/publish/access tests | Đã kiểm thử local |
| Event/job trùng và callback cũ | Pipeline ledger unit tests | Local pass; PostgreSQL/AWS E2E chưa xác minh |
| Cognito/RDS conflict fail closed | Auth/provisioning tests | Offline pass; provisioning PostgreSQL/AWS chưa xác minh |

## Cách tái hiện an toàn

```powershell
# Backend offline, tự đặt fake settings và cấm network
.\.venv\Scripts\python.exe backend\tests\run_unit_offline.py

# Auth/P0 offline; PostgreSQL cases vẫn skip nếu không bật gate
.\.venv\Scripts\python.exe backend\tests\run_auth_offline.py

# AI processors
.\.venv\Scripts\python.exe -m unittest discover -s ai_pipeline\tests -p 'test_*.py'

# Frontend unit/contract
Push-Location .\frontend
npm.cmd test
Pop-Location
```

Không chạy browser/DB/AWS test bằng cách đặt biến production. Mỗi integration module có URL guard/fixture riêng; đọc test và runbook tương ứng trước khi bật. Không dùng `docker-compose.yml` development database làm đích nếu test có thể reset schema hoặc đòi role đặc quyền.

## Điều kiện để ghi “đã xác minh”

- Ghi ngày, commit/artifact, lệnh, môi trường và kết quả pass/fail/skip.
- Với PostgreSQL: ghi DB test cô lập, version, migrations/constraints và rollback/cleanup; không ghi credential.
- Với AWS: ghi account/environment đã làm sạch, Region, Lambda/state-machine version, execution/request identifiers đã làm sạch và log time window; không ghi token/URL/PII.
- Không dùng ảnh UI thành công để thay negative test authorization, không dùng unit stub để thay S3/Bedrock E2E và không dùng `202 PROCESSING` để kết luận pipeline đã hoàn tất.
