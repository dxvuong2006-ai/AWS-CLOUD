# Database migrations

Thư mục này lưu lịch sử thay đổi PostgreSQL **sau snapshot khởi tạo hiện tại**.
Mọi thay đổi cấu trúc database phải đi cùng một migration có thể review và chạy
lặp an toàn; không chỉnh tay database dùng chung/RDS.

## 1. Trạng thái baseline hiện tại

`database/schema.sql` là bootstrap snapshot cho database mới. Nó tạo toàn bộ
bảng MVP hiện có (gồm progress, quiz, Tutor và flashcard) và ghi hai version
sau vào `schema_migrations`:

| Version | Nội dung |
| --- | --- |
| `0001` | LearnCloud core schema. |
| `0002` | Flashcard, approval state và các constraint/trigger integrity. |

Repository có `0003_reconcile_legacy_schema.sql`. Bốn file lịch sử cùng dùng version
`0004`; không được dùng runner theo version cho tới khi đã chọn kế hoạch reconcile
phù hợp với registry/schema đích. `0010_reconcile_0004_consistency.sql` hội tụ DDL
Backend cần nhưng không sửa bản ghi lịch sử `0004`.
`V1__add_password_hash_to_users.sql` là script legacy riêng, không theo bộ chạy
version bốn chữ số bên dưới.

`V3__add_tutor_remediation_fields.sql` là migration lịch sử kiểu Flyway nên
runner PowerShell bên dưới bỏ qua tên file này. `0006_screen_workflows.sql` bổ
sung `workflow_state`, còn `0012_reconcile_tutor_remediation_columns.sql` là
migration numbered hiện hành để hội tụ đủ ba cột TutorSession trên cả database
bootstrap mới và database nâng cấp cũ.

`0013_sync_progress_completion_on_duration_change.sql` đồng bộ các cờ
`lesson_progress.completed` đã tồn tại và cài trigger để tính lại khi
`lessons.duration_seconds` thay đổi. Migration giữ ngưỡng 10% và đặt cờ sai khi
duration là `NULL` hoặc `0`.

`0014_secure_progress_duration_trigger.sql` secures the 0013 trigger for K4:
the Lambda runtime may update `lessons.duration_seconds` but receives no direct
access to `lesson_progress`. It retains the existing trusted function owner
`learncloud_admin`, uses a fixed schema-qualified body and safe `search_path`,
and does not create or transfer roles. The owner may have broader rights than
the trigger needs, so keep it trusted and the function body static. Review the
migration preflight and run
`backend/tests/integration/test_progress_trigger_permissions_postgres.py` on an
isolated PostgreSQL 16 database before considering it for deployment.

`0004_remove_approved_lesson_status.sql` loại `APPROVED` khỏi CHECK Lesson và
đổi dữ liệu `APPROVED` còn sót thành `PUBLISHED`. Script chưa được tự áp dụng.
Migration này không phụ thuộc file `0003` bị thiếu; nó yêu cầu bảng Lesson và
`schema_migrations` của bootstrap hiện tại đã tồn tại. File tiếp theo dùng số
version chưa được dùng trong repository/database chung.
Không tạo lại `0001`/`0002`, và không thêm script cố đánh dấu lại hai version đó
sau khi đã chạy `schema.sql`.

Với DB đã có dữ liệu, không chạy lại `schema.sql` để nâng cấp CHECK: lệnh
`CREATE TABLE IF NOT EXISTS` không sửa constraint của bảng đã tồn tại.

`0005_video_pipeline_ledger.sql` đã được review, **chưa tự áp dụng**. Tạo upload
intents/processing ledger, ghi version 0005 cùng transaction và ràng buộc composite
upload/lesson. Yêu cầu 0004 đã ghi/validated; không thay đổi migration 0004.
Đây là file **one-time**: tự từ chối chạy lại hoặc nhận schema tồn tại không rõ lịch sử;
bộ chạy registry bên dưới sẽ bỏ qua version đã có. Không drop/adopt bảng cũ để ép pass.
Chạy [preflight chỉ đọc](../checks/video_pipeline_preflight.sql) và xem
[review + PowerShell backup/apply/verify](../../docs/video-pipeline-migration-0005.md)
trước khi tự triển khai; không chạy mọi migration chỉ để kiểm tra riêng 0005.

`seed.sql` là dữ liệu demo, không phải migration. Kiểu khóa chính hiện tại là
`SERIAL`/`INTEGER`; migration mới phải khớp kiểu này và các model SQLAlchemy.

## 2. Quy ước

**Tên file:** `NNNN_mo_ta_ngan.sql`, trong đó `NNNN` tăng dần và mô tả viết
thường, dùng dấu gạch dưới.

```text
0004_add_lesson_duration.sql
0005_add_course_slug.sql
0005_add_course_slug.down.sql   <- tùy chọn; script apply bỏ qua file này
```

- Một file là một thay đổi logic, bọc trong `BEGIN; ... COMMIT;`.
- Ưu tiên idempotent: `ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`
  hoặc kiểm tra tồn tại có chủ đích trước khi thay đổi.
- Đặt tên constraint/index rõ ràng: `uq_<bảng>_<ý nghĩa>`,
  `chk_<bảng>_<ý nghĩa>`, `idx_<bảng>_<cột>`.
- Thời gian dùng `TIMESTAMPTZ`; dữ liệu linh hoạt dùng `JSONB` khi cần.
- Chọn `ON DELETE` theo nghiệp vụ, không mặc định `CASCADE` với dữ liệu cần giữ.
- Cột mới `NOT NULL` trên bảng đã có dữ liệu phải có `DEFAULT` hoặc triển khai
  theo ba bước: nullable → backfill → `NOT NULL`.
- Không chứa seed, credential, dữ liệu thật hoặc password trong migration.
- **Không sửa migration đã merge.** Nếu sai, viết migration mới để sửa.

## 3. Template

```sql
-- 0003_add_lesson_duration_label.sql
-- Muc dich: them nhan thoi luong hien thi cho lesson.
-- Anh huong: du lieu cu nhan NULL; khong can backfill ngay.
BEGIN;

ALTER TABLE lessons
    ADD COLUMN IF NOT EXISTS duration_label VARCHAR(32);

INSERT INTO schema_migrations (version, description)
VALUES ('0003', 'add lesson duration label')
ON CONFLICT (version) DO NOTHING;

COMMIT;
```

## 4. Áp dụng migration

Tên container và thông tin kết nối theo `docker-compose.yml`:
`learncloud-db`, database/user `learncloud`, cổng host `5434`.

### Database mới

Trước tiên chạy snapshot; snapshot tự tạo `schema_migrations` và ghi `0001`,
`0002`. Sau đó chạy mọi migration `0003+`, cuối cùng mới seed dữ liệu demo.

```powershell
docker compose up -d learncloud-db

Get-Content .\database\schema.sql -Raw |
  docker exec -i learncloud-db psql -v ON_ERROR_STOP=1 -U learncloud -d learncloud

# Chạy migration 0003+ theo script phía dưới nếu thư mục có file.

Get-Content .\database\seed.sql -Raw |
  docker exec -i learncloud-db psql -v ON_ERROR_STOP=1 -U learncloud -d learncloud
```

### Script PowerShell áp dụng các file còn thiếu

Chạy từ root repository. Script chỉ chạy các file chưa có version trong
`schema_migrations`, theo thứ tự tên file; file `.down.sql` bị bỏ qua.

```powershell
$psql = @("exec", "-i", "learncloud-db", "psql", "-v", "ON_ERROR_STOP=1", "-q", "-U", "learncloud", "-d", "learncloud")

$migrationFiles = Get-ChildItem .\database\migrations -File |
  Where-Object { $_.Name -match '^\d{4}_.+\.sql$' -and $_.Name -notlike "*.down.sql" } |
  Sort-Object Name

$duplicateVersions = $migrationFiles |
  Group-Object { $_.Name.Substring(0, 4) } |
  Where-Object Count -gt 1
if ($duplicateVersions) {
  $details = ($duplicateVersions | ForEach-Object {
    "$($_.Name): $($_.Group.Name -join ', ')"
  }) -join '; '
  throw "Duplicate migration versions require an explicit reviewed plan: $details"
}

$migrationFiles |
  ForEach-Object {
    $version = $_.Name.Substring(0, 4)
    $applied = docker @psql -tAc "SELECT 1 FROM schema_migrations WHERE version = '$version'"
    if (-not $applied) {
      Write-Host "Applying $($_.Name)"
      Get-Content $_.FullName -Raw | docker @psql
    }
  }
```

Sau khi chạy, xác minh:

```powershell
docker exec learncloud-db psql -U learncloud -d learncloud -c "SELECT version, description, applied_at FROM schema_migrations ORDER BY version;"
```

Chạy script lần thứ hai không được áp dụng thêm migration nào.

`0015_user_account_status.sql` requires the canonical 0014 registry row and the
confirmed `learncloud_admin` LOGIN used by the current local Backend configuration.
It grants only missing SELECT/UPDATE privileges on `users.status`; it does not
create roles or grant user-table access to video/AI workers. This source change
does not apply the migration.

## 5. Rollback và phục hồi

- **Local:** nếu không cần giữ dữ liệu, `docker compose down -v`, dựng lại
  database rồi chạy snapshot/migration/seed. Lệnh này xóa toàn bộ volume local.
- **Dùng chung/RDS:** chụp backup/snapshot trước thay đổi. Không rollback bằng
  cách xóa volume/bảng; ưu tiên migration mới theo hướng ngược lại.
- File `.down.sql` là tùy chọn cho thay đổi rủi ro. Chỉ chạy thủ công sau khi
  nhóm đã phê duyệt kế hoạch phục hồi và xác nhận mất dữ liệu chấp nhận được.

## 6. Quy trình PR và checklist review

1. Cập nhật `docs/api-contract.md` nếu request/response bị ảnh hưởng.
2. Chọn số version chưa dùng, tạo migration và cập nhật model/schema Pydantic.
3. Thử trên database sạch và database đã nạp seed.
4. Cập nhật [docs/database.md](../../docs/database.md) trong cùng PR.
5. Review/merge theo thứ tự version; người merge sau đổi version khi xung đột.

- [ ] File có `BEGIN`/`COMMIT` và tự ghi version vào `schema_migrations`.
- [ ] Version không trùng, không sửa migration cũ.
- [ ] Có constraint/index/foreign key cần thiết và `ON DELETE` đúng nghiệp vụ.
- [ ] Chạy lặp an toàn hoặc có hướng dẫn thao tác một lần rõ ràng.
- [ ] Không có secret hoặc dữ liệu mẫu.
- [ ] Code và tài liệu được cập nhật cùng migration.
