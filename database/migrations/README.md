# Database Migrations

Thư mục này lưu **lịch sử thay đổi schema** của PostgreSQL. Mọi thay đổi cấu trúc
DB sau bản baseline đều phải đi qua một file migration, để cả nhóm (và sau này là
RDS trên AWS) có cùng một schema và có thể tái tạo lại từ đầu.

> Người phụ trách: A (nhóm trưởng), review mọi PR có đụng tới `database/`.
> Người cần đổi schema (B, C hoặc D) tự viết file migration cho bảng của mình.

## 1. Hiện trạng

| Phiên bản | Nội dung                                                           | Nguồn                 |
| --------- | ------------------------------------------------------------------ | --------------------- |
| `0001`    | Baseline: `users`, `courses`, `sections`, `lessons`, `enrollments` | `database/schema.sql` |

- `schema.sql` được coi là **migration 0001**. Không sửa file này nữa; thay đổi
  mới viết thành `0002`, `0003`...
- Dữ liệu mẫu nằm ở `database/seed.sql`, **không** thuộc migration (chạy sau cùng).
- Kiểu khóa chính hiện tại là `SERIAL` (integer), không phải UUID như bản đặc tả
  v3. Migration mới phải theo kiểu đang dùng (`INTEGER REFERENCES ...`) để khớp
  với các model SQLAlchemy hiện có.

Các bảng còn thiếu so với mục 5 của tài liệu kiến trúc, dự kiến thành migration
(thứ tự theo phụ thuộc khóa ngoại):

| Dự kiến | Bảng                               | Người làm | Cần trước |
| ------- | ---------------------------------- | --------- | --------- |
| `0002`  | `lesson_progress`                  | B         | tuần 2    |
| `0003`  | `quizzes`, `questions`             | C         | tuần 2    |
| `0004`  | `quiz_attempts`, `quiz_answers`    | C         | tuần 2    |
| `0005`  | `tutor_sessions`, `tutor_messages` | C         | tuần 4    |

Ngoài ra nên bổ sung bằng migration riêng: `CHECK` cho `lessons.status` (8 trạng
thái trong tài liệu), `UNIQUE (section_id, position)` cho `lessons`, và cột
`duration` nếu frontend cần hiển thị thời lượng.

## 2. Quy ước

**Tên file:** `NNNN_mo_ta_ngan.sql`, `NNNN` là số 4 chữ số tăng dần, mô tả viết
thường, nối bằng dấu gạch dưới.

```text
0002_add_lesson_progress.sql
0003_add_quizzes_questions.sql
0003_add_quizzes_questions.down.sql   <- tùy chọn, xem mục 6
```

**Nội dung:**

- Mỗi file là **một thay đổi logic**, bọc trong `BEGIN; ... COMMIT;` để lỗi giữa
  chừng không để lại schema nửa vời.
- Viết sao cho **chạy lại không lỗi** khi có thể: `CREATE TABLE IF NOT EXISTS`,
  `ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`.
- Đặt tên ràng buộc như baseline: `uq_<bảng>_<cột>`, `chk_<bảng>_<ý nghĩa>`.
- Thời gian dùng `TIMESTAMPTZ` (UTC). Dữ liệu linh hoạt dùng `JSONB`.
- Khóa ngoại phải chọn `ON DELETE` có chủ đích (`CASCADE` cho dữ liệu con như
  attempt/progress; không cascade vào dữ liệu cần giữ lại).
- Không đưa dữ liệu mẫu, mật khẩu hay key vào migration.
- Cột mới `NOT NULL` trên bảng đã có dữ liệu phải có `DEFAULT`, hoặc làm theo
  3 bước: thêm cột cho phép NULL → điền dữ liệu → đặt `NOT NULL`.
- **Không sửa migration đã được merge vào `develop`/`main`.** Sai thì viết
  migration mới để sửa.
- Comment trong SQL nên viết không dấu hoặc tiếng Anh nếu nhóm chạy bằng
  Windows PowerShell 5 (pipe có thể làm hỏng mã hóa tiếng Việt).

## 3. Bảng theo dõi `schema_migrations`

Mỗi migration đã áp dụng được ghi vào bảng này, nên script biết file nào đã chạy.

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     VARCHAR(10) PRIMARY KEY,
    description TEXT        NOT NULL,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

Bảng được tạo tự động bởi script ở mục 5. Dòng cuối của **mỗi** file migration
phải tự ghi version của nó (xem template).

## 4. Template migration

```sql
-- 0002_add_lesson_progress.sql
-- Muc dich: luu tien do hoc cua student theo tung lesson.
-- Anh huong: bang moi, khong dong vao du lieu hien co.
BEGIN;

CREATE TABLE IF NOT EXISTS lesson_progress (
    id              SERIAL PRIMARY KEY,
    student_id      INTEGER     NOT NULL REFERENCES users(id)   ON DELETE CASCADE,
    lesson_id       INTEGER     NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    watched_seconds INTEGER     NOT NULL DEFAULT 0,
    completed       BOOLEAN     NOT NULL DEFAULT FALSE,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_lesson_progress_student_lesson UNIQUE (student_id, lesson_id),
    CONSTRAINT chk_lesson_progress_watched_non_negative CHECK (watched_seconds >= 0)
);

CREATE INDEX IF NOT EXISTS idx_lesson_progress_lesson_id ON lesson_progress (lesson_id);

INSERT INTO schema_migrations (version, description)
VALUES ('0002', 'add lesson_progress')
ON CONFLICT (version) DO NOTHING;

COMMIT;
```

## 5. Áp dụng migration

Tên container và thông tin kết nối lấy từ `docker-compose.yml`
(`learncloud-db`, user/db `learncloud`, cổng host `5434`).

### Thiết lập DB mới từ đầu

```bash
docker compose up -d learncloud-db

# 1) baseline
docker exec -i learncloud-db psql -v ON_ERROR_STOP=1 -U learncloud -d learncloud < database/schema.sql
# 2) migration (script bên dưới tự tạo schema_migrations)
# 3) dữ liệu mẫu
docker exec -i learncloud-db psql -v ON_ERROR_STOP=1 -U learncloud -d learncloud < database/seed.sql
```

Ở bước 2, script sẽ ghi `0001` là đã áp dụng nếu thấy bảng `users` đã tồn tại
mà chưa có `schema_migrations` (DB tạo từ `schema.sql` trước khi có thư mục này).

### Script áp dụng các migration còn thiếu

Bash (macOS/Linux/Git Bash), chạy ở thư mục gốc dự án:

```bash
#!/usr/bin/env bash
set -euo pipefail
PSQL="docker exec -i learncloud-db psql -v ON_ERROR_STOP=1 -q -U learncloud -d learncloud"

$PSQL -c "CREATE TABLE IF NOT EXISTS schema_migrations (
  version VARCHAR(10) PRIMARY KEY, description TEXT NOT NULL,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)"

# DB cũ tạo từ schema.sql: đánh dấu baseline 0001 một lần
if [ -z "$($PSQL -tA -c "SELECT 1 FROM schema_migrations")" ] \
   && [ -n "$($PSQL -tA -c "SELECT to_regclass('public.users')")" ]; then
  $PSQL -c "INSERT INTO schema_migrations (version, description)
            VALUES ('0001', 'baseline from schema.sql') ON CONFLICT DO NOTHING"
fi

for f in database/migrations/[0-9][0-9][0-9][0-9]_*.sql; do
  [ -e "$f" ] || continue
  case "$f" in *.down.sql) continue ;; esac
  v=$(basename "$f" | cut -d_ -f1)
  if [ -z "$($PSQL -tA -c "SELECT 1 FROM schema_migrations WHERE version='$v'")" ]; then
    echo "apply $f"
    $PSQL < "$f"
  fi
done
echo "done"
```

PowerShell (Windows):

```powershell
$psql = @("exec","-i","learncloud-db","psql","-v","ON_ERROR_STOP=1","-q","-U","learncloud","-d","learncloud")

docker @psql -c "CREATE TABLE IF NOT EXISTS schema_migrations (version VARCHAR(10) PRIMARY KEY, description TEXT NOT NULL, applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)"

$any = docker @psql -tA -c "SELECT 1 FROM schema_migrations"
$hasUsers = docker @psql -tA -c "SELECT to_regclass('public.users')"
if (-not $any -and $hasUsers) {
  docker @psql -c "INSERT INTO schema_migrations (version, description) VALUES ('0001','baseline from schema.sql') ON CONFLICT DO NOTHING"
}

Get-ChildItem .\database\migrations -Filter "[0-9][0-9][0-9][0-9]_*.sql" |
  Where-Object { $_.Name -notlike "*.down.sql" } | Sort-Object Name | ForEach-Object {
    $v = $_.Name.Substring(0,4)
    $done = docker @psql -tA -c "SELECT 1 FROM schema_migrations WHERE version='$v'"
    if (-not $done) {
      Write-Host "apply $($_.Name)"
      Get-Content $_.FullName -Raw | docker @psql
    }
  }
```

### Kiểm tra sau khi áp dụng

```bash
docker exec -it learncloud-db psql -U learncloud -d learncloud \
  -c "SELECT version, description, applied_at FROM schema_migrations ORDER BY version" \
  -c "\dt"
```

Chạy lại script lần hai phải không áp dụng thêm file nào.

## 6. Rollback

- **Máy local:** cách nhanh nhất là xóa volume và dựng lại
  (`docker compose down -v`, rồi làm lại mục 5). Mất toàn bộ dữ liệu local.
- **Môi trường dùng chung / RDS:** không rollback bằng cách xóa. Chụp snapshot
  trước khi áp dụng, và nếu cần hoàn tác thì viết **migration mới** đi ngược lại.
- File `NNNN_xxx.down.sql` là tùy chọn, dùng cho thay đổi rủi ro (xóa/đổi kiểu
  cột). Script ở mục 5 bỏ qua file `.down.sql`; chạy tay khi cần và xóa dòng
  tương ứng trong `schema_migrations`.

## 7. Quy trình khi cần đổi schema

1. Cập nhật `docs/api-contract.md` nếu thay đổi làm đổi request/response, và báo
   người bị ảnh hưởng (theo quy tắc trong mục review của kiến trúc).
2. Tạo nhánh `feature/<chữ cái>-<việc>`, thêm file migration với số tiếp theo.
   Hai người cùng thêm `0003` thì người merge sau đổi số.
3. Chạy migration trên DB sạch (mục 5) **và** trên DB đã có dữ liệu seed.
4. Cập nhật model SQLAlchemy (`backend/app/models/`) và `docs/database.md`.
5. Mở PR nhỏ (migration + model + docs đi cùng nhau). A review, merge vào `develop`.
6. Mọi người pull về và chạy lại script mục 5.

### Checklist review của A

- [ ] Tên file đúng quy ước, số version không trùng và liền kề.
- [ ] Có `BEGIN/COMMIT` và tự ghi vào `schema_migrations`.
- [ ] Chạy lại lần hai không lỗi, không mất dữ liệu.
- [ ] Ràng buộc (`UNIQUE`, `CHECK`, `FOREIGN KEY`) khớp mục 5 của tài liệu kiến trúc.
- [ ] Model SQLAlchemy và `docs/database.md` được cập nhật cùng PR.
- [ ] Không có dữ liệu mẫu, key, mật khẩu trong file.
- [ ] Không sửa file migration cũ đã merge.

## 8. Không làm

- Không sửa DB bằng tay (pgAdmin, `psql` trực tiếp) mà không có migration tương ứng.
- Không dùng `DROP TABLE`/`DROP COLUMN` trên môi trường dùng chung khi chưa có
  snapshot và chưa báo cả nhóm.
- Không dùng `Base.metadata.create_all()` trong code ứng dụng để tạo bảng; schema
  chỉ đến từ thư mục này.
