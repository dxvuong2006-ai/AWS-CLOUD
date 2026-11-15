# Repository Cleanup & Finalization Report

## 1. Thông tin thực hiện

- Ngày: 15/11/2026 (Asia/Saigon)
- Workspace: `D:\projects\main projects\AWS-CLOUD`
- Nhánh: `develop`
- Baseline sau khi đồng bộ local remote-tracking ref: `5d99256` - merge hotfix
  `feature/d-backend-final`
- Phạm vi: cleanup repository, chuẩn hóa tài liệu và verification local; không
  thay đổi AWS, RDS, Cognito, S3, không chạy migration, không deploy, không
  commit/push.

## 2. Mục tiêu

Chuẩn bị repository để nhóm review/commit/push và bàn giao, đồng thời bảo toàn
hotfix Admin/Cognito đã triển khai, migrations, tests, lịch sử kiểm thử và phần
AI Pipeline của Tuấn. Cleanup được giữ tối thiểu, có thể kiểm tra bằng Git diff
và không xóa dữ liệu local/backup chưa rõ ownership.

## 3. Tài liệu và source đã kiểm tra

- Git status, index, toàn bộ 561 file tracked ban đầu, untracked/modified/staged,
  branch graph, commit history và file history.
- `agent/input/PROGRESS_2_AWS_FINAL.pdf`: kiểm tra tồn tại/hash; bản ở root
  `PROGRESS_2_AWS_FINAL (1).pdf` trùng byte-for-byte. Môi trường không có Poppler
  hoặc thư viện PDF nên không trích xuất lại nội dung PDF trong lượt này.
- `agent/output/LEARNCLOUD_AWS_INVENTORY_FINAL.md` và các báo cáo Admin/Auth.
- `BACKEND_REGRESSION_REPORT.md`.
- `backend/app/api/admin.py`.
- `backend/app/services/auth_service.py`.
- `backend/tests/unit/test_authorization_p0.py`.
- `database/checks/account_status_0015_postflight.sql` và lịch sử commit liên
  quan; không chạy file SQL.
- `README.md`, `docs/local-setup.md`, `docs/aws-deployment.md`, API contract,
  migration guide và cấu trúc `docs/`/`agent/output/`.
- Nội dung/hashes trong `learncloud-lambda.zip` bằng cách đọc archive local;
  không upload/deploy artifact.

## 4. Audit Git và baseline source

### 4.1 Trạng thái ban đầu

Sau khi checkout ban đầu:

- 561 file tracked.
- 0 modified, 0 staged, 0 untracked.
- Local `develop` đứng sau `origin/develop` 79 commit.

Working tree sạch nên nhánh được fast-forward bằng remote-tracking ref đã có
sẵn trong local, không fetch/pull mạng. Việc này đưa source tới merge commit
`5d99256`, chứa hotfix `43ca73b`. Không có thay đổi chưa commit nào bị discard.

### 4.2 Source Lambda/hotfix

Theo baseline bàn giao của nhóm, backend đang chạy Lambda version 6. Lượt
cleanup không gọi AWS nên không xác minh độc lập version/alias/code hash trên
Lambda. Bằng chứng local đã xác minh:

- Commit `43ca73b` thay thao tác enable/disable Cognito từ email sang
  `users.cognito_sub` ổn định.
- `app/api/admin.py` và `app/services/auth_service.py` trong
  `learncloud-lambda.zip` trùng SHA-256 với source hiện tại.
- SHA-256 package local:
  `3335a94fdf202e2d9753bc640423c5c666fb7bd1f4506dfbffc5a109d976b963`.
- Không sửa `admin.py`, `auth_service.py` hoặc `test_authorization_p0.py` trong
  cleanup.

Kết luận: source/package local bảo toàn hotfix đã bàn giao; việc khẳng định
package này chính là code của Lambda version 6 vẫn cần metadata AWS read-only
hoặc deployment record có version/hash trong đợt xác minh riêng.

## 5. Review bốn file trọng yếu

| File | Kết quả review |
| --- | --- |
| `backend/app/api/admin.py` | Cả thao tác chính và rollback dùng `cognito_sub`; không còn truyền email vào `admin_set_user_enabled`. Giữ nguyên. |
| `backend/app/services/auth_service.py` | Cognito `Username` dùng `cognito_sub`; phù hợp mapping danh tính ổn định. Giữ nguyên. |
| `backend/tests/unit/test_authorization_p0.py` | Assertion đã chuyển sang `cognito_sub` và có test email thay đổi nhưng subject vẫn giữ nguyên. Giữ nguyên. |
| `database/checks/account_status_0015_postflight.sql` | Hotfix commit đã vô tình thay toàn bộ postflight read-only bằng `BEGIN; DELETE ...` nhắm tới một account cụ thể, không có `COMMIT`. Đã khôi phục postflight read-only từ parent commit; không chạy SQL và không sửa migration `0015`. |

## 6. Artifact, cache, log, backup và tài liệu cũ

### 6.1 `learncloud-lambda.zip`

File được Git theo dõi vì từng được add trong commit backup `3c6037b`, sau đó
cập nhật ở các commit CORS/package/hotfix; `.gitignore` cũ không có rule cho
artifact này. Binary deployment package không có diff review hữu ích, dễ lệch
source và làm repository phình to.

Đã thực hiện `git rm --cached -- learncloud-lambda.zip`:

- chỉ bỏ file root này khỏi Git index;
- file local vẫn tồn tại;
- SHA-256 trước/sau không đổi;
- `.gitignore` mới ngăn package bị add lại.

### 6.2 Phân loại còn lại

| Nhóm | File/thư mục | Xử lý |
| --- | --- | --- |
| Cache | `.pytest_cache/`, `__pycache__/`, `.mypy_cache/`, `.ruff_cache/` | Ignore; không xóa vì không cần và cache hiện có báo giới hạn quyền đọc. |
| Build | `build/`, `dist/`, `.vite/`, coverage output | Ignore; frontend build sau verification nằm local, không tracked. |
| Log/temp/editor | `*.log`, `*.tmp`, `*.temp`, `*.bak`, `*.orig`, `*~`, `.idea/`, OS metadata | Ignore; không xóa file backup local. |
| Test DB | `backend/tests.db` (272 KiB, vẫn tracked) | Đã thêm ignore cho lần tạo mới, nhưng chưa untrack để tránh xóa khỏi lịch sử khi chưa xác nhận fixture/ownership. |
| Lambda artifacts | `backend/learncloud-lambda.zip`, `learncloud-lambda-auth-sync.zip`, `learncloud-lambda-cors.zip` | Vẫn tracked; đã thêm ignore, đề nghị xác nhận rồi untrack ở commit riêng. |
| AI handoff | `person_c_full.zip` | Giữ nguyên và không ignore tổng quát `*.zip` để bảo toàn phần của Tuấn/người C. |
| Duplicate doc | `PROGRESS_2_AWS_FINAL (1).pdf` | Trùng SHA-256 với `agent/input/PROGRESS_2_AWS_FINAL.pdf`; chưa xóa/untrack vì là tài liệu bàn giao. |
| Test history | `BACKEND_REGRESSION_REPORT.md`, `agent/output/*.md` | Giữ nguyên; không xóa lịch sử kiểm thử/audit. |

Không có file vật lý nào bị xóa và không có file nào bị di chuyển.

## 7. Tài liệu đã chuẩn hóa

- `README.md`: cập nhật baseline bàn giao, cấu trúc repository, lệnh test/build,
  bản đồ tài liệu và ranh giới source/deployment/verification.
- `docs/local-setup.md`: loại hướng dẫn mâu thuẫn về `X-Demo-User` và việc chạy
  cố định migration `0003`; bổ sung setup/test offline và guard không trỏ RDS.
- `docs/aws-deployment.md`: đánh dấu rõ đây là runbook, không phải inventory;
  thay mô tả source lỗi thời (placeholder/missing handler) bằng deployment gates
  hiện hành và provenance artifact.
- `.gitignore`: bổ sung Python/Node cache, build/coverage, log/temp, test DB và
  các Lambda package có tên xác định. Không dùng rule `*.zip` để tránh che khuất
  archive có ownership chưa rõ.

Các tài liệu lịch sử trong `agent/output/` không bị rewrite; nội dung cũ vẫn là
snapshot theo ngày, không phải trạng thái hiện tại.

## 8. Secrets review

Đã quét tracked files hiện tại và 178 commit trong toàn bộ refs local bằng các
mẫu độ tin cậy cao, chỉ ghi rule/path và không xuất giá trị:

- AWS access key ID;
- private key block;
- GitHub/OpenAI/Slack token;
- Google API key.

Kết quả: không phát hiện candidate theo các mẫu trên. `.env` local được ignore;
lịch sử path đã kiểm tra chỉ thấy `.env.example`/`frontend/.env.example`, không
thấy `.env` thật. Các example chứa tên biến nhạy cảm nhưng dùng placeholder và
không được coi là credential.

Giới hạn: `gitleaks`, `trufflehog` và `detect-secrets` không có trong môi trường;
regex audit không chứng minh tuyệt đối lịch sử không từng có secret định dạng
lạ. Khuyến nghị chạy một scanner chuyên dụng trong CI trước khi push public và
rotate ngay nếu chủ repo có bằng chứng credential từng bị commit.

## 9. Kết quả kiểm thử sau cleanup

### Backend

Lệnh chạy từ `backend/` với SQLite in-memory, AWS credential giả, bỏ AWS profile
và tắt pytest cache:

```text
464 passed, 69 skipped, 163 warnings, 9 subtests passed in 36.39s
```

- 0 fail/error.
- Số pass tăng từ baseline 463 lên 464 do hotfix đã bổ sung test subject ổn
  định khi email thay đổi.
- 69 skip vẫn là PostgreSQL opt-in gates; không chạy migration hoặc kết nối DB.
- Warning chủ yếu là FastAPI `on_event`, HTTPX shortcut, Mangum event loop và
  dependency deprecation; không gây test fail.

### Frontend

```text
79 passed, 0 failed, 0 skipped
vite build: success, 734 modules transformed
```

Build có warning dependency `use client` và chunk JavaScript lớn hơn 500 kB;
không có lỗi. Tối ưu code splitting là việc P2 riêng, không thuộc cleanup.

### Kiểm tra repository

- `git diff --check`: pass; chỉ có thông báo line-ending LF/CRLF theo cấu hình
  Git trên Windows.
- Link tương đối trong các Markdown đã sửa: không có target bị thiếu.
- Secret-pattern scan trên các file thay đổi: không có candidate độ tin cậy cao.
- `ai_pipeline/` và `database/migrations/`: không có diff.
- Ba file source/test hotfix: không có diff.

## 10. Danh sách thay đổi cleanup

### Đã sửa

- `.gitignore`
- `README.md`
- `database/checks/account_status_0015_postflight.sql`
- `docs/aws-deployment.md`
- `docs/local-setup.md`
- `agent/output/REPOSITORY_CLEANUP_REPORT.md`

### Đã bỏ khỏi Git index, giữ local

- `learncloud-lambda.zip`

### Đã xóa vật lý

- Không có.

### Đã di chuyển

- Không có.

## 11. Vấn đề chưa giải quyết và đề xuất tiếp theo

1. Review diff và xác nhận staged deletion của `learncloud-lambda.zip` trước
   commit; artifact local đang được ignore và vẫn có thể dùng để đối chiếu.
2. Xác nhận ownership trước khi untrack ba Lambda ZIP còn lại và
   `backend/tests.db`; không gộp quyết định này vào commit cleanup nếu chưa rõ.
3. Xác nhận có thể loại bản PDF root trùng `agent/input/` và các tài liệu
   progress root khỏi index; hiện chưa xóa để giữ lịch sử bàn giao.
4. Trong deployment tiếp theo, ghi commit SHA + artifact SHA-256 + Lambda
   version/alias vào release record; không commit package ZIP trở lại.
5. Chạy PostgreSQL integration gates chỉ khi có database test cô lập đúng guard.
6. Cân nhắc thêm gitleaks/detect-secrets vào CI; không cần rewrite Git history
   nếu scanner chuyên dụng vẫn không phát hiện secret.

## 12. Kết luận

Repository đã được cleanup ở mức tối thiểu và có thể review bằng Git diff.
Hotfix Admin/Cognito, toàn bộ migrations, tests và AI Pipeline được bảo toàn;
không có thay đổi nghiệp vụ/kiến trúc, không thao tác AWS/DB và không
commit/push. Backend/frontend verification đều pass trong phạm vi local an toàn.
