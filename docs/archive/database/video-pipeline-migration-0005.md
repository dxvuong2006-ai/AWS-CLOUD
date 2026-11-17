# [Lịch sử] Review migration 0005 - ledger pipeline video

> **TÀI LIỆU LỊCH SỬ - KHÔNG XÁC MINH HIỆN TẠI.** Thời điểm áp dụng: review và test local ngày 31/10/2026. Migration history hiện có nhiều nhánh `0004`; không chạy lệnh bên dưới nếu chưa đối chiếu [thiết kế database hiện tại](../../02-architecture/database-design.md), registry, target và backup.

> Tài liệu review và lệnh mẫu từ snapshot trước. Chưa xác minh trạng thái 0005 trên bất kỳ database hiện tại nào. Không chạy lệnh migration trực tiếp trước khi xác nhận target, backup và preflight theo quy trình hiện hành.

Snapshot lịch sử ghi migration 0005 chưa được thực thi khi review; trạng thái database
hiện tại chưa xác minh. Các lệnh dưới đây là ví dụ vận hành cần đối chiếu lại với guard
và cấu hình test hiện hành trước khi chạy.

## Kết luận đối chiếu 4 điểm

| Điểm | Đã có trong code trước review | Thay đổi lần này |
| --- | --- | --- |
| Version 0005 | Migration chưa ghi registry. | INSERT version + description ở cuối cùng transaction; kiểm tra 0004, version conflict và bảng tồn tại trước DDL. |
| Upload confirmation | Snapshot review mô tả upload intent và kiểm object tại claim. | Source hiện tại cũng có `POST /lessons/{lesson_id}/confirm-upload`; xem [API contract](../../02-architecture/api-contract.md). Cơ chế pipeline hiện hành cần đối chiếu source/infra riêng. |
| Hai upload/run ghi cùng Lesson; job cũ ghi đè | Course → Lesson FOR UPDATE NOWAIT; claim chỉ khi DRAFT/retry_count=0; callback kiểm execution owner + attempt=retry_count + raw upload identity. | Giữ cơ chế; tăng kiểm tra upload/lesson qua repository; thêm regression tests và PostgreSQL tests cho lock/callback cũ. |
| Hai FK riêng không bảo đảm cùng Lesson | Service tạo run theo upload.lesson_id, nhưng DB chưa ràng buộc cặp. | UNIQUE video_uploads(id, lesson_id) và FK run(upload_id, lesson_id) → upload(id, lesson_id); đồng bộ ORM/repository/service/Lambda path/tests. |

`video_uploads` là **intent**, không phải biên nhận video hợp lệ. Không suy confirmed
từ việc row tồn tại, `raw_video_key` có giá trị hoặc FAILED run tồn tại: nhánh lỗi
validation cũng lưu key và ledger FAILED/UPLOAD_VALIDATION_FAILED để báo lỗi an toàn.
Trong luồng xử lý hiện tại, xác nhận hợp lệ là bước `claim` kiểm object rồi chấp nhận
run. Không có yêu cầu audit timestamp riêng, nên chưa thêm `confirmed_at` trùng nghĩa.
Nếu sau này cần confirmation độc lập từ frontend/audit, phải review contract/migration
mới; không tự đổi kiến trúc trong lần sửa này.

Hai presigned URLs hợp lệ có thể được cấp cho cùng Lesson DRAFT. **Claim hợp lệ đầu
tiên thắng**, không có quy tắc URL xin sau nhất thắng. Claim còn lại bị IGNORE sau
khi lấy khóa và đọc lại trạng thái. Đây là hành vi hiện tại được giữ nguyên.
Mỗi retry tăng retry_count trong transaction với QUEUED outbox; output dùng prefix
upload-id/attempt riêng. `verify_output` giữ khóa khi kiểm owner/generation/raw identity,
đợi job COMPLETE, HEAD output, rồi ghi processed_video_key. Callback attempt cũ bị
STALE_EXECUTION, không ghi lại key hay hạ trạng thái attempt mới. Runtime C cũng phải
tuân thủ cùng ownership gate; quyền ghi SQL tùy ý ngoài service không được coi là an toàn.

## Migration đã được rà soát

File [0005_video_pipeline_ledger.sql](../../../database/migrations/0005_video_pipeline_ledger.sql):

- Một transaction, lock_timeout 5s, statement_timeout 60s, schema `public` rõ ràng.
- Yêu cầu version/description 0004 đúng và ck_lessons_status đã validated, có APPROVED.
  Không cần version 0003; không sửa file 0004 hay status CHECK của Lesson.
- Khóa registry schema_migrations để tránh hai tiến trình đăng ký migration đồng thời.
  DDL thêm foreign key cũng cần khóa bảng cha; có thể chờ/chặn ghi Lesson, nên không
  coi đây là zero downtime. lock_timeout giới hạn thời gian chờ khóa.
- Từ chối nếu 0005 đã ghi hoặc một trong hai bảng đã tồn tại; không tự nhận schema cũ,
  không drop/recreate bảng, không bỏ qua khác biệt bằng CREATE TABLE IF NOT EXISTS.
- Tạo hai bảng, constraints/indexes và INSERT registry 0005 trong cùng transaction.
- Thêm composite FK; giữ NOT NULL cho hai thành phần nên không có đường bỏ qua bằng NULL.
  Giữ chính sách không cascade xóa ledger. Không cập nhật Lesson/Course/seed.
- ORM còn được đồng bộ các CHECK size/attempt/state và partial outbox index vốn đã
  có trong SQL. Không thêm UNIQUE lesson_id hoặc partial active-run index không cần thiết.

Đây là migration **one-time, không reapply trực tiếp**. Chạy lại sẽ dừng trước DDL;
bộ chạy theo registry bỏ qua version đã có. Nếu môi trường nào đã chạy bản 0005 cũ
hoặc có bảng ledger chưa ghi version, dừng ở preflight và review migration sửa riêng;
không sửa registry bằng tay để hợp thức hóa schema chưa kiểm chứng.
Theo [PostgreSQL composite foreign keys](https://www.postgresql.org/docs/16/ddl-constraints.html),
cặp tham chiếu cần một unique key tương ứng trên bảng cha; PK riêng id vẫn được giữ.

## Preflight chỉ đọc

File [video_pipeline_preflight.sql](../../../database/checks/video_pipeline_preflight.sql)
chạy trong REPEATABLE READ READ ONLY, có timeout, không DDL/DML hoặc ghi version.
Nó in DB/role/version, quyền cần thiết, trạng thái Lesson/Course dạng tổng hợp,
columns/constraints/indexes nếu bảng có; không in presigned URL, credentials hay nội dung AI.

- **READY_TO_APPLY:** 0004 hợp lệ, chưa có 0005, cả hai bảng chưa tồn tại.
- **ALREADY_APPLIED:** registry/constraints bắt buộc khớp; mismatch upload–lesson=0;
  không chạy lại migration. Ngay sau apply mới, hai bảng phải rỗng.
- **STOP:** thiếu/khác 0004, version conflict, bảng tồn tại chưa có registry, schema
  một phần, constraint thiếu/sai hoặc dữ liệu tham chiếu sai. Điều tra, không xóa dữ liệu.

Preflight không thay cho backup, kiểm tra quyền owner/LOCK hay việc chạy thử trên bản sao.
Thông tin privilege CREATE/REFERENCES/INSERT giúp đối chiếu, không tự cấp quyền.
[READ ONLY](https://www.postgresql.org/docs/16/sql-set-transaction.html) là cơ chế PostgreSQL
chặn DDL/DML trong transaction này. Dùng psql ON_ERROR_STOP để trả mã lỗi khi có STOP.

## PowerShell — sao lưu, áp dụng, xác minh thủ công

Các ví dụ chạy từ repository root, container `learncloud-db`, database/user `learncloud`
theo compose hiện có. **Agent chưa chạy bất kỳ lệnh Docker/psql/pg_dump nào.** Không chạy
schema.sql/seed.sql trên development để “nâng cấp”; không chạy lại 0004 đã được áp dụng.

### 1. Dừng thay đổi dữ liệu, xem source và chạy preflight

Người vận hành chọn maintenance window, giữ VIDEO_PIPELINE_ENABLED=false, tạm dừng
request ghi dữ liệu khi cần so baseline trước/sau. Nếu pipeline đã hoạt động ở một
môi trường khác, xử lý job đang chạy bằng quy trình riêng trước, không sửa bản cũ tại chỗ.

```powershell
$ErrorActionPreference = 'Stop'
$pipelineContainer = 'learncloud-db'
$pipelineDatabase = 'learncloud'
$pipelineDbUser = 'learncloud'

Get-Content .\database\migrations\0005_video_pipeline_ledger.sql -Encoding UTF8 -Raw
Get-Content .\database\checks\video_pipeline_preflight.sql -Encoding UTF8 -Raw |
  docker exec -i $pipelineContainer psql -X -v ON_ERROR_STOP=1 -P pager=off -U $pipelineDbUser -d $pipelineDatabase
if ($LASTEXITCODE -ne 0) { throw 'Preflight STOP: inspect errors; do not apply.' }
```

Chỉ tiếp tục khi đúng DB, READY_TO_APPLY, 0004 đúng, có đủ quyền và không có bảng
ledger/version conflict. Ghi lại tổng số Lesson/Course theo trạng thái để đối chiếu.
ALREADY_APPLIED nghĩa là bỏ qua bước apply, không phải lý do ghi đè hai bảng.

### 2. Sao lưu archive và kiểm tra archive

Tạo custom-format dump **bên trong container**, sau đó docker cp ra host. Không pipe
binary pg_dump qua PowerShell `>`/Out-File vì có thể làm hỏng encoding trên bản shell cũ.

```powershell
$pipelineStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$pipelineBackupDir = Join-Path (Get-Location).Path 'build\db-backups'
New-Item -ItemType Directory -Force -Path $pipelineBackupDir | Out-Null
$pipelineArchiveInContainer = "/tmp/learncloud-before-0005-$pipelineStamp.dump"
$pipelineBackupFile = Join-Path $pipelineBackupDir "learncloud-before-0005-$pipelineStamp.dump"

docker exec $pipelineContainer pg_dump -U $pipelineDbUser -d $pipelineDatabase -Fc -f $pipelineArchiveInContainer
if ($LASTEXITCODE -ne 0) { throw 'pg_dump failed; do not apply.' }
docker exec $pipelineContainer pg_restore --list $pipelineArchiveInContainer
if ($LASTEXITCODE -ne 0) { throw 'Archive cannot be read; do not apply.' }
docker cp "${pipelineContainer}:${pipelineArchiveInContainer}" $pipelineBackupFile
if ($LASTEXITCODE -ne 0) { throw 'Backup copy failed; do not apply.' }
Get-Item -LiteralPath $pipelineBackupFile | Select-Object FullName, Length
Get-FileHash -LiteralPath $pipelineBackupFile -Algorithm SHA256
```

Archive có dữ liệu nhạy cảm: giữ private, ngoài Git; build/ đã được ignore. Giữ thêm
bản sao an toàn ngoài container. pg_restore --list chỉ kiểm khả năng đọc TOC; nên thử
restore trên DB test riêng trước apply. [pg_dump -Fc](https://www.postgresql.org/docs/16/app-pgdump.html)
là backup một database; không bao gồm toàn bộ roles/globals của cluster.

### 3. Khuyến nghị thử trước trên database test riêng

Chỉ người vận hành thực hiện, trong database mới do mình sở hữu. Không drop/overwrite
database test có sẵn mà chưa review. Không dùng --clean trên development.

```powershell
$pipelineTestDatabase = 'learncloud_pipeline_test'
docker exec $pipelineContainer createdb -U $pipelineDbUser -O $pipelineDbUser $pipelineTestDatabase
if ($LASTEXITCODE -ne 0) { throw 'Test DB already exists or cannot be created; review separately.' }
docker exec $pipelineContainer pg_restore --exit-on-error --no-owner --no-privileges -U $pipelineDbUser -d $pipelineTestDatabase $pipelineArchiveInContainer
if ($LASTEXITCODE -ne 0) { throw 'Test restore failed; development DB was not restored/overwritten.' }

Get-Content .\database\checks\video_pipeline_preflight.sql -Encoding UTF8 -Raw |
  docker exec -i $pipelineContainer psql -X -v ON_ERROR_STOP=1 -U $pipelineDbUser -d $pipelineTestDatabase
if ($LASTEXITCODE -ne 0) { throw 'Test preflight failed.' }
Get-Content .\database\migrations\0005_video_pipeline_ledger.sql -Encoding UTF8 -Raw |
  docker exec -i $pipelineContainer psql -X -v ON_ERROR_STOP=1 -U $pipelineDbUser -d $pipelineTestDatabase
if ($LASTEXITCODE -ne 0) { throw 'Test migration failed; do not apply to development.' }
Get-Content .\database\checks\video_pipeline_preflight.sql -Encoding UTF8 -Raw |
  docker exec -i $pipelineContainer psql -X -v ON_ERROR_STOP=1 -U $pipelineDbUser -d $pipelineTestDatabase
if ($LASTEXITCODE -ne 0) { throw 'Test verification failed.' }
```

Sau đó chạy PostgreSQL tests ở phần dưới nếu muốn. Các bước này do operator tự chạy;
không được báo PostgreSQL migration verified chỉ từ unit tests/SQL review.

### 4. Chỉ áp dụng migration đã review vào database đích

Chạy sau khi backup và thử bản sao đạt. Biến pipelineDatabase vẫn là DB mục tiêu đã
xác nhận, không dùng script “apply tất cả migrations” cho lần review này.

```powershell
Get-Content .\database\migrations\0005_video_pipeline_ledger.sql -Encoding UTF8 -Raw |
  docker exec -i $pipelineContainer psql -X -v ON_ERROR_STOP=1 -P pager=off -U $pipelineDbUser -d $pipelineDatabase
if ($LASTEXITCODE -ne 0) { throw 'Migration failed; transaction is not committed. Inspect before retrying.' }
```

File tự BEGIN/COMMIT. Không bọc trong BEGIN/ROLLBACK khác để “dry run”: COMMIT trong
file có thể kết thúc transaction ngoài. Lỗi guard/timeout/FK/DDL khiến transaction
không commit; psql thoát và connection đóng sẽ rollback. Không chạy lại tự động hay
INSERT registry bằng tay khi có lỗi. Nếu mất kết nối lúc commit, kiểm tra lại bằng
preflight trước khi quyết định có cần apply hay không.

### 5. Xác minh chỉ đọc sau khi áp dụng

```powershell
Get-Content .\database\checks\video_pipeline_preflight.sql -Encoding UTF8 -Raw |
  docker exec -i $pipelineContainer psql -X -v ON_ERROR_STOP=1 -P pager=off -U $pipelineDbUser -d $pipelineDatabase
if ($LASTEXITCODE -ne 0) { throw 'Post-apply verification failed; keep pipeline disabled.' }

$pipelineVerifySql = @'
BEGIN TRANSACTION READ ONLY;
SELECT version, description, applied_at FROM public.schema_migrations
WHERE version IN ('0004','0005') ORDER BY version;
SELECT count(*) AS uploads FROM public.video_uploads;
SELECT count(*) AS runs FROM public.video_pipeline_runs;
SELECT count(*) AS cross_lesson_runs FROM public.video_pipeline_runs r
JOIN public.video_uploads u ON u.id=r.upload_id WHERE r.lesson_id<>u.lesson_id;
SELECT conname, convalidated, pg_get_constraintdef(oid) AS definition
FROM pg_constraint WHERE conrelid='public.lessons'::regclass AND conname='ck_lessons_status';
COMMIT;
'@
$pipelineVerifySql |
  docker exec -i $pipelineContainer psql -X -v ON_ERROR_STOP=1 -P pager=off -U $pipelineDbUser -d $pipelineDatabase
if ($LASTEXITCODE -ne 0) { throw 'Read-only verification failed.' }
```

Kỳ vọng: ALREADY_APPLIED; version 0004 giữ nguyên, 0005 có đúng description; composite
FK/unique/checks đã validated; hai bảng mới rỗng; cross_lesson_runs=0; tổng Lesson/Course,
status/retry/key giữ nguyên so baseline khi application đã tạm dừng ghi. Không tự tạo
upload/run mẫu trong development để chứng minh constraint. Chỉ bật pipeline sau khi
source/DB/schema/network đã cùng sẵn sàng; xem [hướng dẫn AWS lưu trữ](../aws/video-pipeline-console-setup.md).

Nếu apply có vấn đề sau commit: giữ feature flag tắt, xem preflight và roll-forward
migration đã review. Không drop ledger/xóa version 0005 để rollback vội. Backup restore
toàn DB có thể mất dữ liệu phát sinh sau backup, cần quyết định và kế hoạch riêng của
chủ dữ liệu; ví dụ restore ở trên chỉ dành cho DB test mới.

## Kiểm thử và giới hạn kết quả

Unit tests an toàn, không network:

```powershell
.venv/Scripts/python.exe backend/tests/run_unit_offline.py
```

Kết quả review ngày 31/10/2026: **132 unit tests PASS**. SQLite in-memory bật FK đã
từ chối run trỏ upload của Lesson khác. Có tests first valid claim wins, old callback
sau output mới, Lambda guard, original upload-time validation ở retry, ORM/SQL parity,
preflight read-only và guard không cho PostgreSQL suite vào development/remote target.
Migration 0004 không có diff; các API upload/playback/retry/approve/publish regression vẫn đạt.

[PostgreSQL integration tests](../../../backend/tests/integration/test_video_pipeline_ledger_db.py)
được **chuẩn bị, chưa chạy** trong phiên agent. Có 6 tests: registry/constraints,
composite FK thật, hai upload cùng Lesson, khóa NOWAIT với hai connections, unique
upload+attempt và callback cũ không ghi đè key mới. Chúng không chạy DDL/migrations,
không gọi AWS; service commit chỉ release savepoint, outer transaction rollback.

Chỉ operator tự chạy sau khi restore + áp dụng reviewed migration trên test DB riêng.
Suite chỉ chấp nhận tên `learncloud_pipeline_test` tại localhost/127.0.0.1/::1, không
fallback DATABASE_URL development. Cần hai Lesson DRAFT trống trong Course DRAFT thuộc
Instructor, chưa có upload intent; nếu thiếu, chuẩn bị bằng ứng dụng trỏ vào DB test.
Tests không tự sửa fixtures của development hoặc tự seed/bootstrap.

Chạy trong **PowerShell riêng dành cho tests**, không dùng shell đang chạy backend:

```powershell
$env:LEARNCLOUD_PIPELINE_TEST_DATABASE_URL = 'postgresql+psycopg2://learncloud:<URL-ENCODED-TEST-PASSWORD>@127.0.0.1:5434/learncloud_pipeline_test'
$env:JWT_SECRET_KEY = 'isolated-test-placeholder-at-least-32-characters'
$env:LEARNCLOUD_RUN_PIPELINE_DB_TESTS = '1'
Push-Location .\backend
try {
  ..\.venv\Scripts\python.exe -m unittest discover -s tests/integration -p 'test_video_pipeline_ledger_db.py' -v
  if ($LASTEXITCODE -ne 0) { throw 'Isolated PostgreSQL tests failed; inspect before rollout.' }
} finally {
  Pop-Location
}
```

Nhập password test qua cách quản lý secret của nhóm, không commit/in log. Database
test là bản sao có dữ liệu: giữ private. Chưa chạy các lệnh này thì chưa có kết quả
kiểm chứng migration trên PostgreSQL, lock runtime hoặc AWS integration.

## File thay đổi trong lần rà soát

- `database/migrations/0005_video_pipeline_ledger.sql`
- `database/checks/video_pipeline_preflight.sql`
- `backend/app/models/video_pipeline.py`
- `backend/app/repositories/video_pipeline_repo.py`
- `backend/app/services/video_pipeline_service.py`
- `infrastructure/lambda/video_pipeline_handler.py` (ghi rõ contract giữ nguyên; gọi service guard chung)
- `backend/tests/unit/test_video_pipeline.py`
- `backend/tests/unit/test_video_pipeline_migration.py`
- `backend/tests/integration/test_video_pipeline_ledger_db.py`
- `database/migrations/README.md`; tài liệu tổng hợp hiện nay là `docs/02-architecture/database-design.md`
- `docs/aws-video-pipeline-console-setup.md`, tài liệu review này.

Không sửa migration 0004, ASL, cấu trúc event, endpoint upload/confirm/retry hoặc kiến
trúc dispatch. Không thêm confirmed_at, active_run_id, trigger ghi Lesson hay auto-migrate.
