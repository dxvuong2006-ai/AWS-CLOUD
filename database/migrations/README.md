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

Migration `0003_reconcile_legacy_schema.sql` bổ sung các cột mà database cũ
có thể chưa có, gồm `password_hash`, timestamp của course/section và các trường
bổ sung của lesson. Chạy migration này sau snapshot để nâng cấp database hiện
có mà không xóa dữ liệu. Các migration tiếp theo bắt đầu từ **`0004_...sql`**.
Không tạo lại `0001`/`0002`, và không thêm script cố đánh dấu lại hai version đó
sau khi đã chạy `schema.sql`.

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

Get-ChildItem .\database\migrations -Filter "[0-9][0-9][0-9][0-9]_*.sql" |
  Where-Object { $_.Name -notlike "*.down.sql" } |
  Sort-Object Name |
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
